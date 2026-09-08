# Open Hybrid Enterprise AI OS — 최종 Roadmap

## 1. 제품 정의

### Open, Verifiable Enterprise AI Operating System

Cloud, Private Cloud, On-Premise, Air-Gapped 환경에서 동일한 AI Runtime을 실행할 수 있는 **Open Hybrid Enterprise AI OS**를 목표로 한다.

핵심 가치:

**Build → Connect → Contextualize → Verify → Execute → Evaluate**

```text
┌─────────────────────────────────────────────────────────┐
│                    AI APPLICATION LAYER                 │
│  Chat │ AI App │ Agent │ Workflow │ API │ Automation   │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                  AI OS CONTROL PLANE                    │
│ Agent Registry │ Workflow │ Model │ MCP │ Policy        │
│ Identity │ Evaluation │ Cost │ Deployment │ Marketplace │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                     TRUST LAYER                         │
│ Decision Provenance │ Policy │ Risk │ Approval │ Audit  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    AGENT RUNTIME                        │
│ Planner │ Executor │ State │ Memory │ Scheduler │ HITL  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                  CONTEXT COMPILER                       │
│ Knowledge │ Memory │ Skills │ Tools │ Context Optimize  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    MCP FIREWALL                         │
│ Authentication │ Permission │ Inspection │ DLP │ Audit  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│                  OPEN ECOSYSTEM                         │
│ MCP │ A2A │ APIs │ Models │ SaaS │ DB │ Legacy Systems │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 핵심 전략

### 2.1 Cloud + On-Prem 동시 지원

On-Premise를 부가 옵션이 아니라 **제품의 핵심 Deployment Mode**로 설계한다.

지원 환경:

- Cloud
- Private Cloud
- On-Premise
- Air-Gapped
- Edge

하나의 코드베이스와 공통 Runtime을 기반으로 각 환경에 배포한다.

### 2.2 Control Plane / Data Plane 분리

#### Control Plane

- Organization
- User
- Agent Registry
- Workflow
- Model Registry
- Policy
- Evaluation
- Marketplace
- Deployment
- Configuration

#### Data Plane

- Agent Runtime
- LLM
- MCP Gateway
- Context
- Memory
- Vector DB
- Documents
- Enterprise Data
- Secrets
- Logs

On-Prem 환경에서는 Data Plane 전체가 고객 데이터센터 내부에서 실행될 수 있어야 한다.

```text
                 AI OS
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
   Control Plane          Data Plane
        │                     │
   Management             Execution
        │                     │
        └──────────┬──────────┘
                   ↓
              Agent Runtime
```

### 2.3 Open Source First

핵심 Runtime을 오픈소스로 제공하고 Cloud/Enterprise Management 기능을 상용화한다.

---

# 3. 최종 기술 Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    EXPERIENCE LAYER                     │
│ Chat │ Agent Builder │ Workflow │ Admin │ Analytics     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  CONTROL PLANE                          │
│ Agent Registry │ Model Registry │ Policy │ Evaluation   │
│ Identity │ Config │ Deployment │ Marketplace            │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    TRUST LAYER                           │
│ Permission │ Policy │ Approval │ Provenance │ Audit     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  AGENT RUNTIME                           │
│ Planner │ Executor │ State │ Memory │ Scheduler │ HITL  │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                 CONTEXT ENGINE                           │
│ Context Compiler │ RAG │ Memory │ Knowledge │ Skills    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    MCP LAYER                             │
│ MCP Gateway │ Firewall │ Auth │ Permission │ DLP        │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   MODEL LAYER                            │
│ Cloud LLM │ Local LLM │ VLM │ Embedding │ Reranker      │
└───────────────────────────┬─────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│              ENTERPRISE SYSTEMS                         │
│ DB │ ERP │ CRM │ Groupware │ File │ Legacy │ API        │
└─────────────────────────────────────────────────────────┘
```

---

# 4. 개발 원칙

1. **API-first**
2. **MCP-native**
3. **Model-agnostic**
4. **Cloud-agnostic**
5. **Container-first**
6. **Kubernetes-compatible**
7. **Offline-capable**
8. **Modular Monolith부터 시작**
9. **Open Source-first**
10. **Control Plane / Data Plane 분리**
11. **Security / Policy / Audit를 초기부터 고려**
12. **AI-Native Development**

---

# 5. 전체 Roadmap

## Phase 0 — Architecture & Foundation

### 기간: Week 1~2

### 목표

Cloud / Private Cloud / On-Prem / Air-Gapped를 동일한 제품 구조로 지원할 수 있는 기반을 확정한다.

### 개발

- Monorepo
- CI/CD
- Docker
- PostgreSQL
- Redis
- FastAPI
- React / Next.js
- OpenTelemetry
- Authentication
- 기본 API

### Architecture

```text
apps/
├── web
├── api
└── worker

packages/
├── runtime
├── workflow
├── context
├── memory
├── mcp
├── policy
├── evaluation
└── sdk

infra/
├── docker
└── kubernetes
```

### 산출물

- Architecture Specification
- Repository Structure
- CI/CD
- Docker Compose
- 기본 Web/API 실행 환경

---

# 6. Phase 1 — Agent Runtime

### 기간: Week 3~5

AI OS의 핵심 실행 엔진을 구현한다.

```text
User
 ↓
Agent
 ↓
Model
 ↓
Tool
 ↓
Observation
 ↓
Model
 ↓
Result
```

### 기능

- Agent
- Agent Version
- Run
- Task
- State
- Streaming
- Retry
- Timeout
- Cancellation
- Error Handling

### 핵심 API

```text
POST /agents
GET /agents
POST /agents/{id}/run
GET /runs/{id}
POST /runs/{id}/cancel
```

### 핵심 요구사항

인터넷 없이도 Runtime 자체가 실행 가능해야 한다.

---

# 7. Phase 2 — Enterprise MCP Gateway

### 기간: Week 6~8

MCP를 AI OS의 기본 Connectivity Layer로 사용한다.

```text
Agent
 ↓
MCP Gateway
 ↓
Policy
 ↓
Permission
 ↓
MCP Server
 ↓
Enterprise System
```

### 기능

- MCP Client
- MCP Server
- MCP Gateway
- Tool Discovery
- Tool Schema
- Authentication
- Permission
- Connection Management

### 초기 Integration

- GitHub
- Slack
- PostgreSQL
- HTTP
- Filesystem

### 목표

단순 MCP Proxy가 아니라 **Enterprise MCP Gateway**로 발전시킨다.

---

# 8. Phase 3 — Context Compiler / RAG

### 기간: Week 9~12

AI OS의 핵심 차별화 기술을 구축한다.

```text
Enterprise Data
       ↓
Connector
       ↓
Indexer
       ↓
Embedding
       ↓
Vector DB
       ↓
Context Compiler
       ↓
Agent
```

### v1

- System Context
- Conversation
- Knowledge
- Memory
- Tools

### v1.1

- Context Ranking
- Context Compression
- Token Optimization

### 핵심 KPI

**Task Success / Context Token**

목표는 Context를 많이 넣는 것이 아니라 **최소 Context로 최대 Agent 성능**을 확보하는 것이다.

---

# 9. Phase 4 — Workflow Engine

### 기간: Week 13~16

```text
START
 ↓
Agent A
 ↓
Condition
 ├── TRUE → Agent B
 └── FALSE → Agent C
 ↓
Human Approval
 ↓
Agent D
 ↓
END
```

### Node

- START
- END
- AGENT
- LLM
- MCP
- TOOL
- CONDITION
- PARALLEL
- LOOP
- WAIT
- HUMAN
- APPROVAL
- WEBHOOK
- SCHEDULE

---

# 10. Month 4 — Technical MVP

## 목표: Offline-capable Portable AI Runtime

### 기능

- Agent
- Agent Runtime
- MCP
- Context
- Memory
- Workflow
- CLI
- Basic UI
- Streaming
- Trace

### 반드시 가능한 시나리오

```text
Docker Compose
      ↓
Offline 실행
      ↓
Local LLM
      ↓
Local Vector DB
      ↓
Local MCP
      ↓
Agent 실행
```

### 핵심 KPI

> **Time to First Successful Agent < 10분**

---

# 11. Phase 5 — Visual Agent Builder

### 기간: Month 5

개발자뿐 아니라 일반 사용자도 Agent를 만들 수 있도록 한다.

```text
┌───────────────────────────────────────┐
│ Agent Builder                         │
├──────────┬────────────────┬───────────┤
│ Nodes    │ Canvas         │ Settings  │
│          │                │           │
│ Agent    │  Agent         │ Model     │
│ MCP      │    ↓           │ Tools     │
│ Tool     │   MCP          │ Context   │
│ Human    │                │ Memory    │
│ Condition│                │ Policy    │
└──────────┴────────────────┴───────────┘
```

자연어 기반 Agent 생성:

> "Create a customer support agent."

---

# 12. Phase 6 — Local AI Stack

### 기간: Month 5~6

On-Prem 경쟁력을 확보하기 위한 Model Layer를 구축한다.

### Model Gateway

```text
Model Gateway
│
├── OpenAI-compatible
├── vLLM
├── Ollama
├── llama.cpp
└── Other local inference
```

### Model Registry

- Model
- Version
- Context Window
- Quantization
- GPU Requirement
- License
- Benchmark

### 핵심 원칙

Agent가 특정 LLM에 종속되지 않도록 한다.

---

# 13. Month 6 — Public Beta

Cloud와 On-Prem을 동시에 공개한다.

### Cloud

**AI OS Cloud**

### On-Prem

**AI OS Community Edition**

### 기본 배포

- Docker
- Helm
- Kubernetes

### 필수 기능

- Multi-tenancy
- Workspace
- Authentication
- API Keys
- Usage Tracking
- CLI
- Python SDK
- TypeScript SDK
- Documentation

---

# 14. Phase 7 — Evaluation

### 기간: Month 7

Agent와 Model의 품질을 자동으로 평가한다.

```text
Dataset
 ↓
Agent
 ↓
Test Cases
 ↓
Evaluation
 ↓
Score
```

### 평가 항목

- Task Success
- Tool Accuracy
- Answer Quality
- Latency
- Cost
- Safety
- Policy Compliance

### Regression

```text
Agent Version 1
 ↓
Evaluation
 ↓
Agent Version 2
 ↓
Regression Test
```

---

# 15. Phase 8 — Trust Layer

### 기간: Month 8

Enterprise AI의 핵심 차별화 영역이다.

```text
Agent
 ↓
Intent
 ↓
Evidence
 ↓
Policy
 ↓
Decision
 ↓
Action
 ↓
Outcome
```

### Decision Provenance

각 Agent Action에 대해:

- 무엇을 하려고 했는가
- 어떤 Evidence를 사용했는가
- 어떤 Policy가 적용됐는가
- 어떤 Decision이 내려졌는가
- 어떤 Action이 실행됐는가
- 결과가 무엇이었는가

를 추적한다.

---

# 16. Phase 9 — Policy Engine

### 기간: Month 8~9

Policy-as-Code 기반으로 Agent 행동을 통제한다.

```yaml
policy: refund

when:
  amount > 1000

require:
  approval: manager
```

### 실행 구조

```text
Agent
 ↓
Action Proposal
 ↓
Policy Engine
 ↓
 ├── ALLOW
 ├── BLOCK
 └── APPROVAL
```

---

# 17. Phase 10 — MCP Firewall

### 기간: Month 9

MCP를 통한 외부 시스템 접근을 보안 계층에서 통제한다.

```text
Agent
 ↓
MCP Firewall
 │
 ├── Authentication
 ├── Permission
 ├── Schema Validation
 ├── Parameter Inspection
 ├── Injection Detection
 ├── Data Leakage Detection
 ├── Rate Limit
 ├── Policy
 └── Audit
 ↓
MCP Server
```

### 핵심 제품

**Enterprise MCP Firewall**

---

# 18. Month 9 — Production v1

첫 번째 실제 Enterprise / On-Prem 고객 확보를 목표로 한다.

### 지원 환경

- Linux
- Docker
- Kubernetes
- Private Registry
- Local LLM
- Local DB
- Local Vector DB
- Internal MCP

### 핵심 기능

- Agent
- Workflow
- MCP
- Context
- Memory
- Evaluation
- Trust
- Policy
- Security
- Observability

---

# 19. Phase 11 — Air-Gapped Edition

### 기간: Month 10

일반 On-Prem과 Air-Gapped를 별도 Deployment Mode로 제공한다.

### Air-Gapped 요구사항

- No Internet
- Local Model
- Local Container Registry
- Offline Package
- Offline License
- Offline Update
- Signed Package
- SBOM
- Audit

### Offline Release Bundle

```text
AIOS Release
├── Containers
├── Models
├── Helm Charts
├── Dependencies
├── SBOM
├── Signatures
└── License
```

---

# 20. Offline Update System

```text
Internet Zone
     │
     ↓
Release Bundle
     │
     ↓
Security Scan
     │
     ↓
Signed Package
     │
     ↓
Offline Transfer
     │
     ↓
Customer Registry
     │
     ↓
AI OS Update
```

Air-Gapped 고객이 인터넷 연결 없이도 안전하게 버전 업데이트를 수행할 수 있어야 한다.

---

# 21. Phase 12 — Agent Passport

### 기간: Month 10

Agent의 신뢰성을 표준화한다.

```text
Agent Passport

Version
License
Author
Required MCP
Required Permissions
Data Access
Evaluation Score
Security Score
Cost
Latency
Known Risks
```

예:

```text
Task Success     96.2%
Security         High
Permission Risk  Low
Avg Cost         $0.018
Latency          3.2s
```

---

# 22. Phase 13 — Marketplace

### 기간: Month 10~11

```text
Marketplace
│
├── Agents
├── MCP Servers
├── Skills
└── Templates
```

### Cloud Marketplace

```text
Install Agent
 ↓
Download
```

### On-Prem Private Marketplace

```text
Agent Package
 ↓
Security Scan
 ↓
Admin Approval
 ↓
Private Registry
 ↓
Install
```

---

# 23. Phase 14 — Enterprise Control Plane

### 기간: Month 11

여러 AI Runtime을 중앙에서 관리한다.

```text
             Control Plane
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
     DC #1       DC #2       Cloud
       │           │           │
    Runtime     Runtime     Runtime
```

### 관리 대상

- Agents
- Models
- MCP
- Policies
- Users
- Deployments
- Evaluation
- Audit
- Cost

---

# 24. Month 12 — Global v1.0

## 4가지 Deployment Mode

| Edition | 주요 사용자 | 배포 |
|---|---|---|
| Community | Developer / OSS | Docker |
| Cloud | SMB / Developer | SaaS |
| Enterprise | Enterprise | Private Cloud / VPC / On-Prem |
| Air-Gapped | 금융 / 공공 / 국방 등 | 폐쇄망 |

### Global v1.0 필수 기능

- English-first UX
- Documentation
- CLI
- Python SDK
- TypeScript SDK
- Docker
- Kubernetes
- Cloud
- Multi-tenant
- MCP
- Agent
- Workflow
- Evaluation
- Marketplace
- Billing
- On-Prem Deployment

---

# 25. Phase 15 — Enterprise Expansion

### 기간: Month 13~15

## Deployment

- Cloud
- Private Cloud
- On-Prem
- Air-Gapped
- Edge

## Identity

- SAML
- OIDC
- LDAP
- Active Directory
- SCIM
- SSO

## Security

- RBAC
- ABAC
- Secrets
- Encryption
- Audit
- Network Policy
- Tenant Isolation

## Enterprise Integration

- SAP
- Oracle
- Salesforce
- ServiceNow
- SharePoint
- Microsoft 365
- PostgreSQL
- Oracle DB
- SQL Server
- LDAP
- AD

Connector는 가능하면 직접 개발하기보다 MCP Adapter 생태계로 확장한다.

---

# 26. Phase 16 — AI Governance

### 기간: Month 14~15

```text
AI Governance
│
├── Agent Inventory
├── Model Inventory
├── MCP Inventory
├── Risk
├── Policy
├── Approval
├── Audit
└── Compliance
```

관리자가 다음 질문에 답할 수 있어야 한다.

> "우리 회사에서 어떤 Agent가 어떤 데이터와 시스템에 접근하고 있는가?"

---

# 27. Phase 17 — AI Workforce

### 기간: Month 15

Agent를 Digital Workforce로 관리한다.

```text
AI Workforce
│
├── HR Agent
├── Finance Agent
├── IT Agent
├── Sales Agent
├── Support Agent
└── Developer Agent
```

각 Agent에:

- Role
- Permission
- Skill
- Tools
- Knowledge
- Policy
- Autonomy

를 부여한다.

---

# 28. Phase 18 — Autonomy Control

Agent 자율성을 단계별로 제어한다.

```text
L0
Suggest

L1
Execute with approval

L2
Low-risk autonomous

L3
Policy-bound autonomous

L4
Fully autonomous
```

예:

```text
Research Agent
→ L3

Customer Support
→ L2

Finance
→ L1

Payment
→ L0
```

---

# 29. Phase 19 — Dynamic AI Application

### 기간: Month 16

Agent가 답변만 하는 것이 아니라 업무용 UI/Application을 동적으로 구성한다.

```text
User
 ↓
Agent
 ↓
Dynamic UI
 ↓
Enterprise Action
```

예:

```text
구매요청 #30291

금액: ₩38,000,000
위험도: Medium

[승인]
[반려]
[추가 검토]
```

---

# 30. Phase 20 — Computer Use

### 기간: Month 17~18

Legacy System 자동화를 지원한다.

```text
Agent
 ↓
Policy
 ↓
Risk Engine
 ↓
Computer Use
 ↓
Browser / Desktop
 ↓
Legacy Application
```

### 대상

- Legacy ERP
- Legacy Groupware
- Internal Web
- Desktop Application

### 위험 단계

```text
Read
 ↓
Write
 ↓
Transaction
 ↓
Irreversible
```

위험 수준에 따라 Human Approval을 요구한다.

---

# 31. 최종 18개월 Timeline

| 기간 | 핵심 개발 | 목표 |
|---|---|---|
| W1~2 | Architecture | Cloud/On-Prem 공통 구조 |
| W3~5 | Agent Runtime | Portable Runtime |
| W6~8 | MCP Gateway | Enterprise Connectivity |
| W9~12 | Context/RAG | Private Knowledge |
| W13~16 | Workflow | Agent Orchestration |
| **M4** | **Technical MVP** | **Offline AI OS** |
| M5 | Visual Builder + Local AI | 개발자/사용자 접근성 |
| **M6** | **Public Beta** | **Cloud + On-Prem** |
| M7 | Evaluation | Model/Agent Eval |
| M8 | Trust | Provenance |
| M8~9 | Policy | Policy-as-Code |
| M9 | MCP Firewall | Enterprise Security |
| **M9** | **Production v1** | **첫 On-Prem 고객** |
| M10 | Air-Gap | Zero-Egress |
| M10 | Agent Passport | Trusted Agent |
| M10~11 | Marketplace | Private Marketplace |
| M11 | Control Plane | Multi-Deployment |
| **M12** | **Global v1.0** | **Cloud + Private + On-Prem** |
| M13~15 | Enterprise | Integration / Governance |
| M15 | AI Workforce | Enterprise Agents |
| M14~15 | Autonomy Control | Governed Autonomy |
| M16 | Dynamic App | AI Application |
| M17~18 | Computer Use | Legacy Automation |
| **M18** | **Enterprise AI OS** | **완성형** |

---

# 32. 제품 Edition 전략

## Community Edition

무료 / Open Source

```text
Docker
Local LLM
MCP
Agent
Workflow
Context
Memory
CLI
SDK
```

---

## Enterprise Edition

상용

```text
Kubernetes
SSO
RBAC
Audit
Policy
Private LLM
Private Marketplace
HA
Advanced Governance
Enterprise Support
```

---

## Enterprise Air-Gap Edition

상용 Premium

```text
Everything above

+
No Internet
+
Offline Update
+
Signed Package
+
Private Registry
+
Advanced Security
+
Dedicated Support
```

---

# 33. Open Source / License 전략

## OSS Core — Apache 2.0 우선

- Agent Runtime
- Workflow Core
- MCP Gateway Core
- Context Core
- Evaluation SDK
- CLI
- SDK
- Connector SDK

## Commercial Enterprise Layer

- Advanced Governance
- Enterprise SSO
- SCIM
- Advanced RBAC
- Private Marketplace
- Air-Gap Management
- Central Control Plane
- Enterprise Support

### 핵심 전략

**Runtime은 오픈소스로 확산시키고 Enterprise Management를 수익화한다.**

---

# 34. 수익모델

## Cloud

```text
Subscription
+
Usage
```

## Enterprise

```text
Platform License
+
Deployment / Node
+
Support
```

## Air-Gapped

```text
Annual License
+
Maintenance
+
Enterprise Support
```

## Professional Services

- Installation
- Integration
- Migration
- Customization
- Training
- Consulting

---

# 35. 개발팀

AI-Native Development를 전제로 초기 핵심팀은 5~7명 규모를 목표로 한다.

| 역할 | 인원 |
|---|---:|
| Tech Lead / Architect | 1 |
| Agent / AI Engineer | 2 |
| Backend Engineer | 1 |
| Frontend Engineer | 1 |
| DevOps / Security | 1 |
| Product / Design | 1 |

AI Coding Agent를 적극 활용하되 다음 영역은 사람이 직접 책임진다.

### AI가 적극 담당

- CRUD
- API
- SDK
- UI Components
- MCP Connector
- Unit Test
- Integration Test
- Documentation
- Migration
- Refactoring
- Terraform
- Helm
- CI/CD

### 사람이 책임

- Runtime Architecture
- Security Boundary
- Permission Model
- Multi-tenancy
- Context Architecture
- Policy
- Trust Model
- Product UX
- Reliability

---

# 36. AI-Native Development Process

```text
Product Spec
     ↓
AI Architect
     ↓
AI Coding Agent
     ↓
Implementation
     ↓
AI Test Agent
     ↓
AI Security Agent
     ↓
Human Review
     ↓
CI/CD
     ↓
Production
```

Agent 시스템은 일반 CRUD보다 테스트가 중요하므로 AI가 코드뿐 아니라 테스트와 공격 시나리오도 생성하도록 한다.

---

# 37. 개발 우선순위

## Tier 1 — Core

1. Agent Runtime
2. MCP
3. Context Compiler
4. Workflow
5. CLI / SDK

## Tier 2 — Product-Market Fit

6. Agent Builder
7. Memory
8. Trace
9. Evaluation
10. Cloud

## Tier 3 — 차별화

11. Trust / Decision Provenance
12. Policy-as-Code
13. MCP Firewall
14. Agent Passport
15. Autonomy Control

## Tier 4 — Enterprise

16. SSO
17. SCIM
18. Advanced RBAC
19. Audit
20. Private Cloud
21. On-Prem
22. Air-Gapped

## Tier 5 — Advanced

23. Dynamic AI UI
24. Computer Use
25. Legacy Automation

---

# 38. 핵심 차별화

| 기존 AI Platform | Open Hybrid Enterprise AI OS |
|---|---|
| Cloud 중심 | **Cloud + On-Prem + Air-Gap** |
| Agent 중심 | **Agent + OS** |
| Tool 연결 | **MCP Governance** |
| 실행 추적 | **Decision Provenance** |
| Workflow | **Policy-driven Workflow** |
| LLM 종속 | **Model Agnostic** |
| SaaS | **Portable Runtime** |
| Marketplace | **Trusted Private Marketplace** |
| Agent 자동화 | **Governed AI Workforce** |
| 일반 데이터 | **Enterprise Data Sovereignty** |

---

# 39. 핵심 KPI

## Month 4

**Time to First Successful Agent < 10 min**

## Month 6

**첫 외부 개발자 1,000명 목표**

## Month 9

**Agent Task Success > 90%**

## Month 12

**Production Agent 1,000개+ 목표**

## Month 18

OSS → Agent → MCP → Cloud → Enterprise의 Flywheel 구축

```text
OSS Developers
        ↓
Agents
        ↓
MCP Ecosystem
        ↓
Cloud Users
        ↓
Enterprise
        ↓
More Agents / Connectors
        ↓
More Developers
```

---

# 40. 최종 시장 포지셔닝

## 핵심 메시지

> # Build AI Agents Anywhere.
> ## Cloud. Private Cloud. On-Prem. Air-Gapped.

기술 메시지:

> **One AI OS. Any Model. Any Data. Any Environment.**

### 최종 포지셔닝

**Open + Verifiable + Secure + Contextual + Autonomous**

```text
                    OPEN AI OS
                        │
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
   COMPOSABLE       VERIFIABLE        SECURE
       │                │                │
      MCP          Provenance       MCP Firewall
      A2A          Policy           Permission
      APIs         Evaluation       Autonomy
       │                │                │
       └────────────────┼────────────────┘
                        ↓
                  CONTEXTUAL
                        │
                 Context Compiler
                        │
                        ↓
                   AUTONOMOUS
                        │
                   Agent Runtime
```

---

# 41. 최종 사업 실행 순서

```text
Month 0
   ↓
Architecture
   ↓
Month 4
   ↓
Offline-capable OSS MVP
   ↓
Month 6
   ↓
Public Beta
Cloud + On-Prem
   ↓
Month 9
   ↓
Enterprise Production
첫 On-Prem 고객
   ↓
Month 12
   ↓
Global v1.0
Cloud + Private Cloud + On-Prem + Air-Gap
   ↓
Month 15
   ↓
Enterprise Governance
   ↓
Month 18
   ↓
Full Enterprise AI OS
```

---

# 42. 최종 전략 요약

이 사업은 **Wonderful의 기능을 그대로 복제하는 것이 목표가 아니다.**

Wonderful과 같은 AI OS 시장을 겨냥하되, 다음 문제를 핵심 차별화 영역으로 가져간다.

1. **Cloud Lock-in → Portable AI Runtime**
2. **Agent Black Box → Decision Provenance**
3. **MCP Connectivity → MCP Security / Firewall**
4. **Agent Automation → Policy-driven Autonomy**
5. **Cloud-only → Cloud + Private Cloud + On-Prem + Air-Gap**
6. **Generic Marketplace → Trusted Private Marketplace**
7. **LLM Dependency → Model Agnostic**
8. **AI Assistant → Governed AI Workforce**

최종 목표는 **18개월 안에 Cloud SaaS와 동일한 UX를 제공하면서도 고객 데이터센터와 폐쇄망에서 독립적으로 실행되는 Global Open Hybrid Enterprise AI OS**를 구축하는 것이다.
