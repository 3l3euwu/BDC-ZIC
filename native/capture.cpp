// Process-loopback capture helper. No injection, no session-volume changes.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <propvarutil.h>
#include <stdint.h>
#include <stdio.h>
#include <vector>
#include <algorithm>
#include "effects.hpp"

// audioclientactivationparams.h is not present in all SDKs.
struct LoopbackParams { DWORD type, pid, mode; };
static const wchar_t *device = L"VAD\\Process_Loopback";
struct Completion final : IActivateAudioInterfaceCompletionHandler {
    LONG refs = 1; HANDLE event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    HRESULT result = E_FAIL; IAudioClient *client = nullptr;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id, void **p) override {
        if (!p) return E_POINTER; *p = nullptr;
        if (IsEqualIID(id, IID_IUnknown) || IsEqualIID(id, IID_IActivateAudioInterfaceCompletionHandler) || IsEqualIID(id, IID_IAgileObject)) { *p = static_cast<IActivateAudioInterfaceCompletionHandler*>(this); AddRef(); return S_OK; }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs); }
    ULONG STDMETHODCALLTYPE Release() override { LONG n = InterlockedDecrement(&refs); if (!n) { if (client) client->Release(); CloseHandle(event); delete this; } return n; }
    HRESULT STDMETHODCALLTYPE ActivateCompleted(IActivateAudioInterfaceAsyncOperation *op) override {
        IUnknown *obj = nullptr; HRESULT inner = E_FAIL;
        HRESULT hr = op->GetActivateResult(&inner, &obj);
        result = FAILED(hr) ? hr : inner;
        if (SUCCEEDED(result) && obj) { result = obj->QueryInterface(IID_IAudioClient, (void**)&client); obj->Release(); }
        SetEvent(event); return S_OK;
    }
};
static bool exists(const wchar_t *p) { return GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES; }
static bool publish(const wchar_t *dir, unsigned slot, const int16_t *data, size_t samples) {
    wchar_t tmp[MAX_PATH], dst[MAX_PATH];
    if (swprintf(tmp, MAX_PATH, L"%ls\\chunk.tmp", dir) < 0 || swprintf(dst, MAX_PATH, L"%ls\\chunk%u.pcm", dir, slot) < 0) return false;
    HANDLE f = CreateFileW(tmp, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD n = 0; DWORD bytes = (DWORD)(samples * sizeof(int16_t));
    bool ok = WriteFile(f, data, bytes, &n, nullptr) && n == bytes; CloseHandle(f);
    if (ok) ok = MoveFileExW(tmp, dst, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
    if (!ok) DeleteFileW(tmp);
    return ok;
}
int wmain(int argc, wchar_t **argv) {
    if (argc != 3) { fwprintf(stderr, L"Usage: capture.exe PID STREAM_DIRECTORY\n"); return 2; }
    wchar_t *end = nullptr; unsigned long pid = wcstoul(argv[1], &end, 10);
    if (!pid || !end || *end || pid == GetCurrentProcessId()) { fwprintf(stderr, L"Invalid PID\n"); return 2; }
    wchar_t stop[MAX_PATH]; if (swprintf(stop, MAX_PATH, L"%ls\\stop", argv[2]) < 0) return 2;
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED); if (FAILED(hr)) return 3;
    auto handler = new Completion(); IActivateAudioInterfaceAsyncOperation *operation = nullptr;
    LoopbackParams params{1, (DWORD)pid, 0}; PROPVARIANT pv{}; pv.vt = VT_BLOB; pv.blob.cbSize = sizeof(params); pv.blob.pBlobData = (BYTE*)&params;
    hr = ActivateAudioInterfaceAsync(device, IID_IAudioClient, &pv, handler, &operation);
    if (SUCCEEDED(hr)) { DWORD wait = WaitForSingleObject(handler->event, 10000); hr = wait == WAIT_OBJECT_0 ? handler->result : HRESULT_FROM_WIN32(WAIT_TIMEOUT); }
    if (operation) operation->Release();
    if (FAILED(hr)) { fwprintf(stderr, L"Process-loopback activation failed: 0x%08lx\n", (unsigned long)hr); handler->Release(); CoUninitialize(); return 4; }
    IAudioClient *client = handler->client;
    WAVEFORMATEX fmt{}; fmt.wFormatTag = WAVE_FORMAT_PCM; fmt.nChannels = 2; fmt.nSamplesPerSec = 48000; fmt.wBitsPerSample = 16; fmt.nBlockAlign = 4; fmt.nAvgBytesPerSec = 192000;
    hr = client->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 0, 0, &fmt, nullptr);
    IAudioCaptureClient *capture = nullptr;
    if (SUCCEEDED(hr)) hr = client->GetService(IID_IAudioCaptureClient, (void**)&capture);
    if (SUCCEEDED(hr)) hr = client->Start();
    if (FAILED(hr)) { fwprintf(stderr, L"Audio initialization failed: 0x%08lx\n", (unsigned long)hr); if (capture) capture->Release(); handler->Release(); CoUninitialize(); return 5; }
    std::vector<int16_t> pending; pending.reserve(4800); unsigned slot = 0; bool failed = false;
    wchar_t settings_path[MAX_PATH];
    if (swprintf(settings_path, MAX_PATH, L"%ls\\effects.ini", argv[2]) < 0) { client->Stop(); capture->Release(); handler->Release(); CoUninitialize(); return 2; }
    Effects effects; EffectSettings settings; ULONGLONG last_settings = 0;
    HANDLE process = OpenProcess(SYNCHRONIZE, FALSE, (DWORD)pid);
    fprintf(stdout, "Capturing PID %lu. Stop via panel or stop file.\n", pid); fflush(stdout);
    while (!exists(stop) && (!process || WaitForSingleObject(process, 0) == WAIT_TIMEOUT)) {
        if (GetTickCount64() - last_settings >= 250 || last_settings == 0) {
            // Atomic panel writes; missing file/keys fall back to safe defaults.
            auto read = [&](const wchar_t *key, int fallback, int lo) {
                return clamp_setting((int)GetPrivateProfileIntW(L"effects", key, fallback, settings_path), lo, 10);
            };
            settings.reverb = read(L"reverb", 0, 0); settings.distance = read(L"distance", 0, 0);
            settings.clarity = read(L"clarity", 0, 0); settings.muffle = read(L"muffle", 0, 0);
            settings.size = read(L"size", 0, 0); settings.stereo = read(L"stereo", 0, 0);
            settings.volume = read(L"volume", 5, 1); last_settings = GetTickCount64();
        }
        UINT32 frames = 0; hr = capture->GetNextPacketSize(&frames); if (FAILED(hr)) { failed = true; break; }
        while (frames) {
            BYTE *buf = nullptr; UINT32 count = 0; DWORD flags = 0;
            hr = capture->GetBuffer(&buf, &count, &flags, nullptr, nullptr); if (FAILED(hr)) { failed = true; break; }
            const int16_t *stereo = reinterpret_cast<const int16_t*>(buf);
            for (UINT32 i=0; i<count; ++i) {
                const bool silent = (flags & AUDCLNT_BUFFERFLAGS_SILENT) != 0;
                pending.push_back(effects.process(silent ? 0 : stereo[i*2], silent ? 0 : stereo[i*2+1], settings));
            }
            capture->ReleaseBuffer(count);
            while (pending.size() >= 2400) { publish(argv[2], slot, pending.data(), 2400); slot = (slot + 1) % 8; pending.erase(pending.begin(), pending.begin()+2400); }
            if (failed) break;
            hr = capture->GetNextPacketSize(&frames); if (FAILED(hr)) { failed = true; break; }
        }
        if (failed) break; Sleep(10);
    }
    if (failed) fwprintf(stderr, L"Capture or file write failed: 0x%08lx\n", (unsigned long)hr);
    if (process) CloseHandle(process); client->Stop(); capture->Release(); handler->Release(); CoUninitialize(); return failed ? 6 : 0;
}
