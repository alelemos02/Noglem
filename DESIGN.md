# Design System — JulIA (Noglem)

## Product Context
- **What this is:** Plataforma centralizada de agentes de IA especializados para engenharia de instrumentacao e automacao industrial
- **Who it's for:** Engenheiros tecnicos de instrumentacao, automacao e controle
- **Space/industry:** Enterprise AI tools para engenharia industrial
- **Project type:** Web app (dashboard) + landing page

## Memorable Thing
"Plataforma que eu confiaria dados criticos." Toda decisao de design serve este objetivo. Confianca se comunica por restricao, nao por decoracao.

## Aesthetic Direction
- **Direction:** Industrial Precision
- **Decoration level:** Minimal — zero graficos decorativos. Nada de blobs, gradientes, ilustracoes abstratas. O produto e o protagonista.
- **Mood:** Painel de controle de engenharia. Nao um brinquedo. Cada elemento justifica sua existencia por funcao, e a beleza vem da precisao. Um engenheiro que vir esta pagina deve pensar: "essas pessoas levam o trabalho tao a serio quanto eu."
- **Reference sites:** Linear (restraint), Stripe (trust), Sentry (directness)

## Typography
- **Brand/Logo:** Rajdhani 700, tracked wide, uppercase — DNA tecnico, mantido da identidade original
- **Display/Hero:** DM Sans 600, 44-48px, letter-spacing -0.8px — autoridade sem "pitch deck energy"
- **Headings:** DM Sans 500, 18-24px, letter-spacing -0.3px
- **Body:** Source Sans 3 400, 16px — feita pra UI tecnica, engenheiros ja confiam nela de spec sheets
- **UI/Labels:** DM Sans 500, 12-13px
- **Data/Tables:** IBM Plex Mono 500 tabular-nums — diz "este numero e preciso" como nenhuma outra mono
- **Captions/System:** IBM Plex Mono 400, 10-11px, letter-spacing 1.5px, uppercase
- **Loading:** Google Fonts CDN
  ```
  https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=IBM+Plex+Mono:wght@400;500;600&family=Rajdhani:wght@500;600;700&family=Source+Sans+3:wght@300;400;500;600&display=swap
  ```
- **Scale:**
  | Token       | Size  | Weight | Font           | Use                    |
  |-------------|-------|--------|----------------|------------------------|
  | display     | 48px  | 600    | DM Sans        | Hero, page titles      |
  | heading-lg  | 24px  | 500    | DM Sans        | Section headings       |
  | heading     | 18px  | 500    | DM Sans        | Card titles, subheads  |
  | body-lg     | 17px  | 400    | Source Sans 3  | Hero description       |
  | body        | 16px  | 400    | Source Sans 3  | Default body text      |
  | body-sm     | 14px  | 400    | Source Sans 3  | Secondary content      |
  | ui          | 13px  | 500    | DM Sans        | Buttons, nav items     |
  | label       | 12px  | 500    | DM Sans        | Form labels            |
  | data        | 14px  | 500    | IBM Plex Mono  | Numbers, metrics       |
  | caption     | 11px  | 400    | IBM Plex Mono  | Timestamps, status     |
  | eyebrow     | 11px  | 500    | IBM Plex Mono  | Section labels (upper) |

## Color
- **Approach:** Restrained. Cor e funcional, nao decorativa. Mapeada ao modelo mental de engenheiros (DCS/SCADA: azul=nominal, verde=ok, amber=atencao, vermelho=erro).

### Dark Mode (default)
| Role             | Hex/Value                      | Use                                    |
|------------------|--------------------------------|----------------------------------------|
| bg-primary       | `#0A0F1A`                      | Navy-black, tela de SCADA              |
| bg-secondary     | `#111827`                      | Cards, paineis                         |
| surface          | `#1A2235`                      | Elementos elevados, containers         |
| surface-hover    | `#243049`                      | Hover state                            |
| border           | `#2A3650`                      | Divisores, bordas de cards             |
| border-strong    | `#3A4660`                      | Bordas com mais enfase                 |
| text-primary     | `#E2E8F0`                      | Branco quente (nao #FFF clinico)       |
| text-secondary   | `#8899B4`                      | Steel blue-gray                        |
| text-tertiary    | `#5A6B8A`                      | Captions, timestamps                   |
| text-disabled    | `#3A4660`                      | Elementos desabilitados                |
| accent           | `#14B8A6`                      | Teal — nominal, ativo, verificado      |
| accent-hover     | `#0D9488`                      | Hover do accent                        |
| accent-muted     | `rgba(20, 184, 166, 0.12)`    | Background tint para accent elements   |
| success          | `#22C55E`                      | Operacao concluida                     |
| success-muted    | `rgba(34, 197, 94, 0.08)`     | Background sutil de success            |
| warning          | `#EAB308`                      | Amber industrial — atencao             |
| warning-muted    | `rgba(234, 179, 8, 0.06)`     | Background sutil de warning            |
| error            | `#EF4444`                      | SOMENTE erros. Nunca decoracao.        |
| error-muted      | `rgba(239, 68, 68, 0.06)`     | Background sutil de error              |
| info             | `#06B6D4`                      | Informacional secundario               |
| info-muted       | `rgba(6, 182, 212, 0.06)`     | Background sutil de info               |

### Light Mode
| Role             | Hex/Value                      |
|------------------|--------------------------------|
| bg-primary       | `#F8FAFC`                      |
| bg-secondary     | `#F1F5F9`                      |
| surface          | `#FFFFFF`                      |
| surface-hover    | `#F1F5F9`                      |
| border           | `#CBD5E1`                      |
| border-strong    | `#94A3B8`                      |
| text-primary     | `#0F172A`                      |
| text-secondary   | `#475569`                      |
| text-tertiary    | `#94A3B8`                      |
| accent           | `#0D9488`                      |
| accent-hover     | `#0F766E`                      |
| accent-muted     | `rgba(20, 184, 166, 0.08)`    |

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)
- **Section separation:** 64px
- **Card interior padding:** 20-24px
- **Button padding:** 8-10px vertical, 18-22px horizontal

## Layout
- **Approach:** Asymmetric left-heavy briefing document
- **Grid:** Content starts at ~14-15% left margin on desktop. NOT centered.
- **Max content width:** 1100px
- **Border radius:** xs:3px, sm:5px, md:6px, lg:8px, xl:10px. Nunca `rounded-full` em containers.

### Landing Page Structure
1. **Nav:** Logo (Rajdhani) top-left, botoes ghost + primary top-right. Sem mega-menus.
2. **Hero:** Eyebrow (IBM Plex Mono, uppercase, text-tertiary) + titulo unico left-aligned (DM Sans 600, 44-48px) + descricao + CTA unico teal. SEM pill badge, SEM gradiente, SEM subheading poetico.
3. **Status strip:** Grid 4x2 mostrando os 8 agentes como chips de status com dot verde. Parece manifesto de sistema, nao feature grid.
4. **Tool bands:** Cada ferramenta em banda horizontal full-width. Lado esquerdo: nome + descricao. Lado direito: screenshot real do output. Separadas por regras finas (border). SEM cards com icones decorativos.
5. **Metrics table:** Tabela real com metricas da plataforma (docs processados, precisao, tempo, uptime). Engenheiros confiam em tabelas.
6. **CTA final:** Botao unico teal + texto "sem cartao de credito". Sem urgencia artificial.
7. **Footer:** Minimo — copyright + versao.

## Motion
- **Approach:** Minimal-functional — so transicoes que ajudam compreensao
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(100ms) short(150ms) medium(200ms)
- **Regra:** Nenhuma animacao de entrada chamativa. Sem pulsacao sem acao do usuario. Sem scroll-driven animations na landing page.

## Component Rules

### Alerts
Fundo escuro uniforme (bg-secondary) + border: 1px solid border + border-left: 2px solid cor-semantica. Texto em text-secondary. NUNCA background colorido. A cor semantica aparece SOMENTE no border-left e no icone.

### Badges
Fundo extremamente mutado (opacidade 6-8%) + texto na cor semantica. Fonte: IBM Plex Mono 10px. Border-radius: 3px.

### Buttons
- Primary: background accent, text white, DM Sans 500, border-radius 6px
- Ghost/Secondary: background transparent, border 1px border, text text-secondary
- Danger: border 1px rgba(239,68,68,0.3), text error. NUNCA background vermelho.

### Data Tables
Headers em IBM Plex Mono 10px uppercase letter-spacing 1px, cor text-tertiary. Numeros em IBM Plex Mono 500 tabular-nums, cor text-primary. Linhas separadas por border, hover sutil em rgba(255,255,255,0.015).

## Do's and Don'ts

### Do
- Usar accent teal SOMENTE para: CTA primario, links interativos, focus ring, status "ativo"
- Usar o surface ladder (bg-primary > bg-secondary > surface > surface-hover) para hierarquia
- Mostrar screenshots reais do produto como protagonistas visuais
- Tratar tabelas de dados como first-class citizens do design
- Manter numeros SEMPRE em IBM Plex Mono tabular-nums
- Alinhar conteudo a esquerda com margem generosa

### Don't
- Nunca usar accent teal como background de secao ou fill de card
- Nunca adicionar graficos decorativos (blobs, gradientes, ilustracoes abstratas)
- Nunca usar vermelho para nada que nao seja erro real
- Nunca centralizar hero com pill badge — isso grita "gerado por IA"
- Nunca usar grid 3 colunas de features com icones em quadrados coloridos
- Nunca usar backgrounds coloridos em alertas (so border-left)
- Nunca usar animacoes de entrada chamativas ou scroll-triggered
- Nunca usar Inter, Space Grotesk, Roboto, Poppins ou Montserrat

## Responsive Behavior

### Breakpoints
| Name       | Width  | Key Changes                                      |
|------------|--------|--------------------------------------------------|
| Desktop    | 1100px | Default layout, left-aligned                     |
| Tablet     | 768px  | Status grid 4x2 > 2x4, tool bands stack vertical |
| Mobile     | 480px  | Single column, display 48px > 28px               |

### Touch Targets
- CTAs: min 40px height
- Status chips: min 36px height
- Form inputs: min 40px height

## Decisions Log
| Date       | Decision                              | Rationale                                                |
|------------|---------------------------------------|----------------------------------------------------------|
| 2026-05-24 | Accent: teal #14B8A6                  | Azul generico rejeitado como "mais do mesmo". Teal = display de instrumento, diferenciado |
| 2026-05-24 | Kill orange-red #FF4D2D               | Laranja grita "consumer startup". Vermelho reservado so pra erros |
| 2026-05-24 | Alertas monocromaticos                | Alertas coloridos rejeitados como "colorido demais". Border-left only |
| 2026-05-24 | Layout left-aligned briefing          | Hero centralizado + grid de features = "cara de IA". Briefing = documento tecnico |
| 2026-05-24 | Typography: DM Sans + Source Sans 3   | Inter/Space Grotesk substituidos. Source Sans 3 = confianca de spec sheet |
| 2026-05-24 | IBM Plex Mono para dados              | JetBrains Mono substituido. Plex Mono = enterprise systems |
| 2026-05-24 | Navy-black #0A0F1A background         | Pure black #0A0A0C substituido. Subtom azul = tela de SCADA |
