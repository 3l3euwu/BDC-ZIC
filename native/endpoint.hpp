#pragma once
#include <mmdeviceapi.h>
#include <endpointvolume.h>
#include <functiondiscoverykeys_devpkey.h>
#include <string>

struct EndpointMute {
    IMMDeviceEnumerator *enumerator = nullptr;
    IAudioEndpointVolume *volume = nullptr;
    std::wstring id;
    bool changed = false;
};

// Fail closed if a default device cannot be checked. An absent default role is OK.
static HRESULT endpoint_is_default(IMMDeviceEnumerator *enumerator, const wchar_t *id, bool *is_default) {
    *is_default = false;
    for (int role = eConsole; role <= eCommunications; ++role) {
        IMMDevice *device = nullptr;
        HRESULT hr = enumerator->GetDefaultAudioEndpoint(eRender, (ERole)role, &device);
        if (hr == HRESULT_FROM_WIN32(ERROR_NOT_FOUND)) continue;
        if (FAILED(hr)) return hr;
        LPWSTR default_id = nullptr; hr = device->GetId(&default_id); device->Release();
        if (FAILED(hr)) return hr;
        if (!_wcsicmp(default_id, id)) *is_default = true;
        CoTaskMemFree(default_id);
    }
    return S_OK;
}
static HRESULT new_enumerator(IMMDeviceEnumerator **out) {
    return CoCreateInstance(CLSID_MMDeviceEnumerator, nullptr, CLSCTX_ALL, IID_IMMDeviceEnumerator, (void**)out);
}
static void print_utf8(const std::wstring &line) {
    int n = WideCharToMultiByte(CP_UTF8, 0, line.c_str(), (int)line.size(), nullptr, 0, nullptr, nullptr);
    if (n <= 0) return;
    std::string bytes((size_t)n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, line.c_str(), (int)line.size(), &bytes[0], n, nullptr, nullptr);
    fwrite(bytes.data(), 1, bytes.size(), stdout);
}
static int list_outputs() {
    IMMDeviceEnumerator *enumerator = nullptr; IMMDeviceCollection *collection = nullptr;
    HRESULT hr = new_enumerator(&enumerator);
    if (SUCCEEDED(hr)) hr = enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &collection);
    UINT count = 0; if (SUCCEEDED(hr)) hr = collection->GetCount(&count);
    for (UINT i = 0; SUCCEEDED(hr) && i < count; ++i) {
        IMMDevice *device = nullptr; LPWSTR id = nullptr; IPropertyStore *properties = nullptr;
        PROPVARIANT name; PropVariantInit(&name);
        hr = collection->Item(i, &device);
        if (SUCCEEDED(hr)) hr = device->GetId(&id);
        if (SUCCEEDED(hr)) hr = device->OpenPropertyStore(STGM_READ, &properties);
        if (SUCCEEDED(hr)) hr = properties->GetValue(PKEY_Device_FriendlyName, &name);
        bool is_default = false;
        if (SUCCEEDED(hr)) hr = endpoint_is_default(enumerator, id, &is_default);
        if (SUCCEEDED(hr)) {
            std::wstring label = name.vt == VT_LPWSTR && name.pwszVal ? name.pwszVal : L"Unnamed output";
            for (auto &c : label) if (c == L'\t' || c == L'\n' || c == L'\r') c = L' ';
            print_utf8(std::wstring(is_default ? L"default\t" : L"available\t") + id + L"\t" + label + L"\n");
        }
        PropVariantClear(&name); if (properties) properties->Release(); if (id) CoTaskMemFree(id); if (device) device->Release();
    }
    if (collection) collection->Release(); if (enumerator) enumerator->Release();
    if (FAILED(hr)) { fwprintf(stderr, L"Could not enumerate output devices: 0x%08lx\n", (unsigned long)hr); return 7; }
    return 0;
}
static HRESULT mute_endpoint(EndpointMute &m, const wchar_t *id) {
    HRESULT hr = new_enumerator(&m.enumerator); IMMDevice *device = nullptr;
    bool is_default = false; DWORD state = 0; BOOL muted = FALSE;
    if (SUCCEEDED(hr)) hr = endpoint_is_default(m.enumerator, id, &is_default);
    if (SUCCEEDED(hr) && is_default) hr = E_ACCESSDENIED;
    if (SUCCEEDED(hr)) hr = m.enumerator->GetDevice(id, &device);
    if (SUCCEEDED(hr)) hr = device->GetState(&state);
    if (SUCCEEDED(hr) && !(state & DEVICE_STATE_ACTIVE)) hr = E_FAIL;
    if (SUCCEEDED(hr)) hr = device->Activate(IID_IAudioEndpointVolume, CLSCTX_ALL, nullptr, (void**)&m.volume);
    if (SUCCEEDED(hr)) hr = m.volume->GetMute(&muted);
    if (SUCCEEDED(hr) && !muted) { hr = m.volume->SetMute(TRUE, nullptr); if (SUCCEEDED(hr)) m.changed = true; }
    if (device) device->Release();
    if (SUCCEEDED(hr)) m.id = id;
    return hr;
}
static HRESULT restore_endpoint(EndpointMute &m) {
    HRESULT hr = S_OK;
    if (m.volume && m.changed) {
        BOOL muted = FALSE; hr = m.volume->GetMute(&muted);
        if (SUCCEEDED(hr) && muted) hr = m.volume->SetMute(FALSE, nullptr);
    }
    if (m.volume) m.volume->Release(); if (m.enumerator) m.enumerator->Release();
    m.volume = nullptr; m.enumerator = nullptr; m.changed = false;
    return hr;
}
