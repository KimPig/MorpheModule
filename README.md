# MorpheModule

[![Build](https://github.com/KimPig/MorpheModule/actions/workflows/build.yml/badge.svg)](https://github.com/KimPig/MorpheModule/actions/workflows/build.yml)

KimPig의 YouTube, YouTube Music, Twitter 및 Instagram용 패치 빌드입니다. 각 빌드는 KernelSU/Magisk 모듈과 일반 설치 APK를 모두 생성하며, 결과물은 [Releases](https://github.com/KimPig/MorpheModule/releases)에서 받을 수 있습니다.

## 빌드 구성

| 앱 | 패치 | 버전 | 추가 옵션 | 산출물 |
|---|---|---|---|---|
| YouTube | Morphe stable | 패치가 지원하는 최신 버전 | 기본 패치 | APK + 모듈 |
| YouTube Music | Morphe stable | 패치가 지원하는 최신 버전 | 기본 패치, arm64 | APK + 모듈 |
| Twitter | Piko 3.8.0-dev.6 | 12.7.1-release.0 | `Bring back twitter`, 앱 이름 `Twitter` | APK + 모듈 |
| Instagram | Piko 3.8.0-dev.6 | 435.0.0.37.76 | 기본 패치, arm64 | APK + 모듈 |

Twitter 12.7.1은 Piko가 직접 지원하므로 X-Shim을 사용하지 않습니다. 모듈에는 공식 stock split APK가 포함되어 있어 앱이 없거나 버전이 다를 때 플래시 과정에서 맞는 버전을 설치합니다.

Twitter와 Instagram은 12.2 stable + X-Shim 호환 문제가 해결될 때까지 검증할 Piko 개발 릴리스를 명시적으로 고정해서 사용합니다.

## Instagram 모듈 제한

Instagram Piko 설정을 사용하려면 Release의 일반 설치 APK를 사용하세요.

Piko는 설정, 백업, 복원 및 폴더 선택용 Activity를 patched Manifest에 새로 추가합니다. KernelSU/Magisk 모듈은 stock APK를 Android에 등록한 뒤 patched `base.apk`를 마운트하므로, 새 Activity가 Package Manager에 등록되지 않습니다. 따라서 모듈에서는 앱 자체는 실행되더라도 Piko 설정 화면이 `ActivityHook: launchActivity failure`로 열리지 않습니다.

일반 APK 설치 시에는 patched Manifest가 정상 등록됩니다. 다만 기본 구성은 Clone 패치를 활성화하지 않으므로 공식 Instagram과 서명이 달라 함께 설치할 수 없습니다. 공식 앱을 제거해야 한다면 먼저 필요한 데이터와 로그인 정보를 백업하세요.

## Stock APK 다운로드 순서

Twitter와 Instagram은 다음 순서로 stock APK를 가져옵니다.

1. 이 저장소의 `stock-apks` Release
2. APKMirror
3. Uptodown
4. 모두 실패하거나 패키지·버전·공식 서명 검증에 실패하면 전체 workflow 중지

실패한 공급원이 남긴 부분 파일은 다음 공급원으로 넘기지 않습니다. Workflow 실패 이메일은 GitHub 계정의 Actions 알림 설정이 활성화된 경우에만 전송됩니다.

YouTube와 YouTube Music은 j-hc APK archive를 우선 사용하고, 실패하면 APKMirror와 Uptodown을 차례로 사용합니다.

## 설치 참고

- 일반 설치 YouTube/YouTube Music APK에는 [ReVanced GmsCore](https://github.com/ReVanced/GmsCore)가 필요합니다.
- YouTube/YouTube Music 모듈은 Play Store가 stock 앱을 덮어쓰지 않도록 [zygisk-detach](https://github.com/j-hc/zygisk-detach) 사용을 권장합니다.
- 일반 설치 APK는 공식 앱과 서명이 다르므로 기존 공식 앱 제거가 필요할 수 있습니다.
- 모듈 플래시 화면과 `module.prop`의 저자는 `KimPig`로 표시됩니다.

## 로컬 빌드

Linux에는 Java 17 이상, Python 3, `jq`, `zip`, `unzip`이 필요합니다.

```console
git clone https://github.com/KimPig/MorpheModule.git
cd MorpheModule
python3 -m pip install -r requirements-apkmirror.txt
./build.sh config.toml
```

Termux에서는 다음 명령으로 시작할 수 있습니다.

```console
bash <(curl -sSf https://raw.githubusercontent.com/KimPig/MorpheModule/main/build-termux.sh)
```

설정 항목은 [CONFIG.md](./CONFIG.md)를 참고하세요.

## Credits

- [j-hc/revanced-magisk-module](https://github.com/j-hc/revanced-magisk-module) — 원본 빌더 및 모듈 템플릿
- [MorpheApp/morphe-patches](https://github.com/MorpheApp/morphe-patches)
- [crimera/piko](https://github.com/crimera/piko)
- [REAndroid/APKEditor](https://github.com/REAndroid/APKEditor)

이 저장소의 APKMirror 클라이언트는 외부 downloader 코드를 복사하지 않은 독립 구현이며, Cloudflare challenge가 발생하면 우회하지 않고 다음 공급원으로 넘어갑니다.
