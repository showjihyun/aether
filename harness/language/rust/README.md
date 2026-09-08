# Rust 팩 (최소)

Rust 백엔드 프로젝트에 하네스를 붙일 때 읽습니다. 이 팩은 코어 `detect-stack.sh` 가 원래 제공하던 Rust 감지·기본 단계를 옮긴 **최소 팩**입니다. 문서 예시(`examples.md`, `improvement-log.example.yaml`)는 아직 없으며, 필요할 때 [../_template/](../_template/) 을 따라 추가합니다. 팩 계약은 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | Rust 가 조직 스택에서 사라질 때, 또는 최소 팩을 넘어 예시 문서가 필요해질 때 |

## 감지 조건

| 스택 ID | 근거 파일 |
| --- | --- |
| `rust` | `Cargo.toml` |

## 지원 kind

| kind | 판정 | 디렉터리 |
| --- | --- | --- |
| `backend` | 항상 | [backend/](backend/) |

WASM 프론트엔드는 아직 별도 kind 로 다루지 않습니다.

## 기본 verify 단계

| id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- |
| `build` | `correctness` | true | `cargo build --locked` | 항상 |
| `fmt` | `quality` | false | `cargo fmt --check` | 항상 |
| `clippy` | `quality` | false | `cargo clippy -- -D warnings` | 항상 |
| `deny` | `architecture` | false | `cargo deny check` | `deny.toml` 이 있을 때 |
| `test` | `correctness` | true | `cargo test` | 항상 |

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `clippy.toml`, `.clippy.toml`, `rustfmt.toml`, `.rustfmt.toml` | lint·포맷 규칙 파일입니다 |
| 차단 | `deny.toml`, `.cargo/audit.toml` | 의존성 정책과 취약점 검사 제외 목록입니다 |
| 경고 | `Cargo.toml`, `Cargo.lock`, `.cargo/config.toml`, `build.rs` | 의존성 변경은 정상이지만 feature 플래그로 테스트가 빠지거나 `rustflags` 로 경고가 꺼질 수 있습니다 |
| 보안 | `.cargo/credentials(.toml)` | 레지스트리 토큰입니다 |

## 문서 예시

- [backend/harness.config.example](backend/harness.config.example)
