---
date: 2026-06-02
tags:
  - setup
  - claude-code
  - obsidian
  - windows
  - wsl
  - tool
status: completed
---

# Claude Code 환경 세팅 (Windows 11 + WSL2 + Obsidian)

> [!success] 세팅 완료 일자: 2026-06-02
> PowerShell 기반 Claude Code + oh-my-claudecode + Obsidian Claudian 연동까지 전체 세팅 완료.

---

## 1. 시스템 환경

| 항목 | 값 |
|------|-----|
| OS | Windows 11 Home |
| Shell | PowerShell 5.1 + WSL2 |
| WSL 배포판 | Ubuntu-24.04 (Running) |
| Node.js | v26.3.0 |
| Claude Code CLI | 2.1.160 |
| OpenAI Codex CLI | 0.136.0 |

---

## 2. 필수 사전 설치 항목

### 2-1. Node.js 설치
- https://nodejs.org 에서 LTS 버전 다운로드 후 설치
- PowerShell에서 확인:
```powershell
node --version   # v26.x.x
npm --version
```

### 2-2. WSL2 + Ubuntu 24.04 설치
```powershell
# PowerShell (관리자 권한)
wsl --install -d Ubuntu-24.04

# 설치 확인
wsl --list --verbose
```

### 2-3. Claude Code CLI 설치 (npm 전역)
```powershell
npm install -g @anthropic-ai/claude-code
claude --version   # 2.1.160
```

### 2-4. OpenAI Codex CLI 설치
```powershell
npm install -g @openai/codex
codex --version
```

### 2-5. oh-my-claudecode (OMC) 설치
```powershell
npm install -g oh-my-claude-sisyphus
# 또는 Claude Code 내부에서:
# /oh-my-claudecode:omc-setup
```

---

## 3. Claude Code 플러그인 설치

Claude Code 실행 후 `/` 명령으로 설치. 또는 `settings.json`에 직접 추가.

### 설치된 플러그인 목록

| 플러그인 | 마켓플레이스 | 버전 | 용도 |
|---------|------------|------|------|
| `oh-my-claudecode` | omc | 4.14.4 | 멀티 에이전트 오케스트레이션 |
| `superpowers` | claude-plugins-official | 5.1.0 | 추가 기능 확장 |
| `context7` | claude-plugins-official | latest | 라이브러리 문서 자동 조회 |
| `skill-creator` | claude-plugins-official | latest | 커스텀 스킬 생성 |
| `github` | claude-plugins-official | latest | GitHub 통합 |
| `codex` | openai-codex | 1.0.4 | OpenAI Codex 연동 |

### `~/.claude/settings.json` 내용
```json
{
  "enabledPlugins": {
    "oh-my-claudecode@omc": true,
    "superpowers@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "skill-creator@claude-plugins-official": true,
    "github@claude-plugins-official": true,
    "codex@openai-codex": true
  },
  "extraKnownMarketplaces": {
    "omc": {
      "source": {
        "source": "git",
        "url": "https://github.com/Yeachan-Heo/oh-my-claudecode.git"
      }
    },
    "openai-codex": {
      "source": {
        "source": "github",
        "repo": "openai/codex-plugin-cc"
      }
    }
  },
  "theme": "auto",
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "statusLine": {
    "type": "command",
    "command": "node C:/Users/whqkr/.claude/hud/omc-hud.mjs"
  }
}
```

### `~/.claude/settings.local.json` — 허용된 명령 권한
```json
{
  "permissions": {
    "allow": [
      "Bash(npm i *)",
      "Bash(node *)",
      "Bash(npm install *)",
      "Bash(codex *)",
      "Bash(bash *)",
      "Bash(npm view *)"
    ]
  }
}
```

---

## 4. oh-my-claudecode (OMC) 설정

### OMC 주요 설정값 (`~/.claude/.omc-config.json`)
| 항목 | 값 |
|------|-----|
| 기본 실행 모드 | ultrawork |
| 팀 최대 에이전트 수 | 3 |
| 기본 에이전트 타입 | claude |

### 주요 스킬 / 명령어

| 명령 | 용도 |
|------|------|
| `/oh-my-claudecode:autopilot` | 완전 자동 실행 모드 |
| `/oh-my-claudecode:ralph` | 반복 루프 실행 |
| `/oh-my-claudecode:ultrawork` | 병렬 실행 모드 |
| `/oh-my-claudecode:planner` | 전략적 계획 수립 |
| `/oh-my-claudecode:code-reviewer` | 코드 리뷰 |
| `/oh-my-claudecode:debugger` | 디버깅 |
| `/oh-my-claudecode:cancel` | 현재 실행 중지 |
| `/codex:rescue` | Codex에 작업 위임 |

### 키워드 트리거 (자동 감지)
- `"autopilot"` → autopilot 모드
- `"ralph"` → ralph 루프
- `"ulw"` → ultrawork
- `"ccg"` → Claude+Codex+Gemini 트리오
- `"deep interview"` → 요구사항 정밀 인터뷰
- `"cancelomc"` → 실행 취소

---

## 5. 환경 변수

| 변수명 | 값 | 용도 |
|-------|-----|------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` | 팀 기능 실험적 활성화 |

---

## 6. WSL2 작업 경로

Claude Code는 PowerShell에서 실행하지만, 실제 프로젝트 파일은 WSL2 Ubuntu에 있음.

```
Windows UNC 경로: \\wsl.localhost\Ubuntu-24.04\home\whqkrel\
WSL 내부 경로:    ~/  (= /home/whqkrel/)
```

WSL 명령 실행 방법:
```powershell
# PowerShell에서 WSL 명령 실행
wsl -d Ubuntu-24.04 -- bash -c "명령어"

# 예시: ngspice 실행
wsl -d Ubuntu-24.04 -- bash -c "cd ~/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models && ngspice -b ~/rfic_project/circuits/lc_dco_top.cir"
```

---

## 7. Obsidian + Claudian 연동

### Claudian 플러그인 선택 이유
- Obsidian에서 바로 Claude Code 사용 가능
- 별도 터미널 없이 노트 작성 중 AI 지원
- 현재 작업 컨텍스트(노트 내용) 자동 전달

### 설치 방법
1. Obsidian → Settings → Community Plugins → Browse
2. "Claudian" 검색 후 설치
3. 플러그인 설정에서 Claude API 키 또는 Claude Code 경로 설정

> [!note] Claudian vs 다른 플러그인
> - Claudian: Claude Code CLI 직접 연동 (로컬 실행)
> - Smart Connections: 임베딩 기반 노트 검색 특화
> - Text Generator: GPT 계열 특화

---

## 8. `~/.claude/` 디렉토리 구조

```
C:\Users\whqkr\.claude\
├── settings.json          ← 플러그인 & 환경 설정
├── settings.local.json    ← 로컬 권한 오버라이드
├── CLAUDE.md              ← 전역 코딩 가이드라인
├── .credentials.json      ← API 자격증명 (비공개)
├── .omc-config.json       ← OMC 설정
├── history.jsonl          ← 세션 히스토리
├── .omc/                  ← OMC 상태/계획
├── backups/               ← 설정 백업
├── cache/                 ← 내부 캐시
├── plugins/
│   ├── cache/             ← 플러그인 캐시
│   ├── data/              ← 플러그인 데이터
│   ├── marketplaces/      ← 3개 마켓플레이스
│   │   ├── claude-plugins-official/
│   │   ├── omc/
│   │   └── openai-codex/
│   └── installed_plugins.json
├── projects/              ← 프로젝트별 메모리
└── sessions/              ← 세션 기록
```

---

## 9. 빠른 재설치 체크리스트

새 PC에서 동일 환경 구축 시:

- [ ] Node.js LTS 설치
- [ ] WSL2 + Ubuntu-24.04 설치
- [ ] `npm install -g @anthropic-ai/claude-code`
- [ ] `npm install -g @openai/codex`
- [ ] `npm install -g oh-my-claude-sisyphus`
- [ ] `~/.claude/settings.json` 복원
- [ ] `~/.claude/settings.local.json` 복원
- [ ] `~/.claude/CLAUDE.md` 복원
- [ ] Obsidian 설치 + Claudian 플러그인 설치
- [ ] WSL에서 PDK/프로젝트 파일 복원

---

## 관련 노트
- [[2026-06-02_LC-DCO_Phase2_Progress]]
