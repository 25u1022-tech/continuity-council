{
  "product": {
    "name": "Continuity Council",
    "tagline": "Film production recovery dashboard — disruption in, ranked options out, decision ledger forever.",
    "aesthetic": {
      "mode": "dark-default",
      "style": "Enterprise Cinematic (tuxedo: near-black surfaces + crisp tables + restrained metallic accents)",
      "keywords": [
        "sleek",
        "high-contrast",
        "data-dense",
        "perfect alignment",
        "demo-friendly",
        "audit-grade"
      ]
    },
    "audience": {
      "primary": "Hackathon judges (3-minute demo)",
      "persona": "Hollywood Line Producer / studio ops under time pressure",
      "success_actions": [
        "Report a disruption in <30s",
        "Watch agents investigate (visible orchestration)",
        "See ClickHouse evidence queried live",
        "Approve a recovery option",
        "Verify decision recorded in ledger"
      ]
    }
  },
  "design_references": {
    "inspiration_sources": [
      {
        "name": "Ammo Studio — Showrunnr (Cinematic Hybrid)",
        "url": "https://www.ammo.studio/projects/showrunnr",
        "takeaways": [
          "‘Tuxedo’ feel: authority without heaviness",
          "Cinematic hero moments + operational clarity in dense sections",
          "Use animation/visual cues over screenshot clutter"
        ]
      },
      {
        "name": "ClickHouse console / query log patterns (community consoles)",
        "urls": [
          "https://clickhouse.design/click-ui",
          "https://github.com/daun-gatal/chouse-ui",
          "https://www.shadcn.io/blocks/tables-database-queries"
        ],
        "takeaways": [
          "SQL log panel must feel like a console: monospace, line numbers, copy button",
          "Dense table with status chips + latency + rows returned",
          "Expandable rows for details (profile/events) — mimic via Collapsible"
        ]
      }
    ]
  },
  "layout": {
    "app_shell": {
      "pattern": "Left sidebar + top header",
      "desktop_target": "1920x800",
      "sidebar": {
        "width": "w-[264px]",
        "behavior": "sticky, scroll-independent",
        "nav_items": [
          "Production Dashboard",
          "Report Disruption",
          "Agent Investigation",
          "Recovery Options",
          "Decision Ledger"
        ],
        "active_indicator": "left accent bar + subtle background"
      },
      "header": {
        "height": "h-14",
        "contents": [
          "Production selector chip (static)",
          "Global status badge (open/investigating/options_ready/approved)",
          "Producer user chip (hardcoded)",
          "Quick actions: ‘Report Disruption’ button"
        ]
      },
      "grid": {
        "page_container": "max-w-[1600px] w-full px-4 lg:px-6",
        "main_grid": "grid grid-cols-12 gap-4 lg:gap-6",
        "dense_panels": "Use col-span-12 then split to col-span-7/5 or 8/4 for evidence vs options"
      }
    },
    "screen_blueprints": {
      "production_dashboard": {
        "top_row": "3 KPI cards (Shoot Days, Active Disruptions, Budget at Risk)",
        "main": "10-scene schedule table (shadcn Table) with sticky header + row hover",
        "right_rail": "Cast availability + Location availability cards (compact lists)"
      },
      "report_disruption": {
        "layout": "Two-column form on desktop; single column on mobile",
        "left": "Form fields",
        "right": "Context panel: current schedule + impacted entities preview"
      },
      "agent_investigation": {
        "layout": "Top: investigation progress + timer; Middle: 6 agent status cards; Bottom: MCP call log console",
        "motion": "Polling-driven state transitions + skeleton rows"
      },
      "recovery_options": {
        "layout": "Split view: left Recovery Options (cards) | right Historical Evidence (ClickHouse) table",
        "bottom": "Decision preview strip (selected option summary)"
      },
      "decision_ledger": {
        "layout": "Full-width audit table with filters + row expand for evidence summary"
      }
    }
  },
  "typography": {
    "font_pairing": {
      "display": {
        "name": "Space Grotesk",
        "use": "Headings, navigation, option ranks",
        "google_fonts": "https://fonts.google.com/specimen/Space+Grotesk"
      },
      "body": {
        "name": "Inter",
        "use": "Body, labels, table text",
        "google_fonts": "https://fonts.google.com/specimen/Inter"
      },
      "mono": {
        "name": "IBM Plex Mono",
        "use": "Money, hours, SQL, latency, row counts",
        "google_fonts": "https://fonts.google.com/specimen/IBM+Plex+Mono"
      }
    },
    "scale_tailwind": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg text-muted-foreground",
      "section_title": "text-sm font-semibold tracking-wide uppercase",
      "table": "text-sm leading-5",
      "kpi_value": "text-2xl md:text-3xl font-semibold tabular-nums",
      "micro": "text-xs text-muted-foreground"
    },
    "numerals": {
      "rule": "Use tabular-nums + mono for $ and hours",
      "classes": "font-mono tabular-nums"
    }
  },
  "color_system": {
    "notes": [
      "Dark mode by default.",
      "No purple for AI/agent UI accents.",
      "Gradients only as subtle decorative overlays (<20% viewport).",
      "ClickHouse evidence must have its own visual identity (teal/cyan accent)."
    ],
    "tokens_css_variables": {
      "implementation_location": "/app/frontend/src/index.css",
      "dark_root": {
        "--background": "220 18% 6%",
        "--foreground": "210 20% 96%",
        "--card": "220 18% 8%",
        "--card-foreground": "210 20% 96%",
        "--popover": "220 18% 8%",
        "--popover-foreground": "210 20% 96%",
        "--primary": "210 20% 96%",
        "--primary-foreground": "220 18% 10%",
        "--secondary": "220 14% 14%",
        "--secondary-foreground": "210 20% 96%",
        "--muted": "220 12% 16%",
        "--muted-foreground": "215 12% 70%",
        "--accent": "220 12% 16%",
        "--accent-foreground": "210 20% 96%",
        "--border": "220 12% 18%",
        "--input": "220 12% 18%",
        "--ring": "186 92% 45%",
        "--destructive": "0 72% 48%",
        "--destructive-foreground": "210 20% 96%",
        "--radius": "0.75rem",
        "--chart-1": "186 92% 45%",
        "--chart-2": "38 92% 55%",
        "--chart-3": "142 60% 45%",
        "--chart-4": "210 10% 70%",
        "--chart-5": "0 72% 48%"
      },
      "brand_extras_add_as_custom_vars": {
        "--cc-gold": "44 84% 58%",
        "--cc-teal": "186 92% 45%",
        "--cc-ink": "220 18% 6%",
        "--cc-slate": "220 14% 14%",
        "--cc-panel": "220 18% 8%",
        "--cc-panel-2": "220 14% 12%",
        "--cc-gridline": "220 12% 18%"
      }
    },
    "semantic_accents": {
      "status": {
        "open": {
          "badge": "bg-muted text-foreground border-border",
          "dot": "bg-muted-foreground"
        },
        "investigating": {
          "badge": "bg-[hsl(var(--cc-teal)/0.12)] text-[hsl(var(--cc-teal))] border-[hsl(var(--cc-teal)/0.25)]",
          "dot": "bg-[hsl(var(--cc-teal))]"
        },
        "options_ready": {
          "badge": "bg-[hsl(var(--cc-gold)/0.14)] text-[hsl(var(--cc-gold))] border-[hsl(var(--cc-gold)/0.25)]",
          "dot": "bg-[hsl(var(--cc-gold))]"
        },
        "approved": {
          "badge": "bg-[hsl(142_60%_45%/0.14)] text-[hsl(142_60%_45%)] border-[hsl(142_60%_45%/0.25)]",
          "dot": "bg-[hsl(142_60%_45%)]"
        }
      },
      "severity": {
        "low": "bg-[hsl(142_60%_45%/0.14)] text-[hsl(142_60%_45%)] border-[hsl(142_60%_45%/0.25)]",
        "medium": "bg-[hsl(38_92%_55%/0.14)] text-[hsl(38_92%_55%)] border-[hsl(38_92%_55%/0.25)]",
        "high": "bg-[hsl(0_72%_48%/0.14)] text-[hsl(0_72%_48%)] border-[hsl(0_72%_48%/0.25)]"
      },
      "compliance": {
        "valid": "bg-[hsl(142_60%_45%/0.14)] text-[hsl(142_60%_45%)] border-[hsl(142_60%_45%/0.25)]",
        "invalid": "bg-[hsl(0_72%_48%/0.14)] text-[hsl(0_72%_48%)] border-[hsl(0_72%_48%/0.25)]"
      },
      "clickhouse_identity": {
        "label": "Historical Evidence (ClickHouse)",
        "accent": "teal/cyan",
        "panel_border": "border-[hsl(var(--cc-teal)/0.35)]",
        "panel_bg": "bg-[hsl(var(--cc-teal)/0.06)]",
        "badge": "bg-[hsl(var(--cc-teal)/0.14)] text-[hsl(var(--cc-teal))] border-[hsl(var(--cc-teal)/0.25)]"
      }
    },
    "gradients_and_texture": {
      "allowed_usage": [
        "Only as decorative overlays in header/hero strip or behind page title",
        "Max 20% viewport",
        "Never behind dense tables"
      ],
      "safe_gradient_examples": [
        "radial-gradient(800px circle at 20% 0%, hsl(var(--cc-teal)/0.18), transparent 55%)",
        "radial-gradient(700px circle at 80% 10%, hsl(var(--cc-gold)/0.14), transparent 60%)"
      ],
      "noise_overlay_css": "background-image: radial-gradient(800px circle at 20% 0%, hsl(var(--cc-teal)/0.18), transparent 55%), radial-gradient(700px circle at 80% 10%, hsl(var(--cc-gold)/0.14), transparent 60%), url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"120\" height=\"120\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.9\" numOctaves=\"2\" stitchTiles=\"stitch\"/></filter><rect width=\"120\" height=\"120\" filter=\"url(%23n)\" opacity=\"0.06\"/></svg>');"
    }
  },
  "components": {
    "component_path": {
      "shadcn_primary": [
        "/app/frontend/src/components/ui/table.jsx",
        "/app/frontend/src/components/ui/card.jsx",
        "/app/frontend/src/components/ui/badge.jsx",
        "/app/frontend/src/components/ui/button.jsx",
        "/app/frontend/src/components/ui/separator.jsx",
        "/app/frontend/src/components/ui/tabs.jsx",
        "/app/frontend/src/components/ui/scroll-area.jsx",
        "/app/frontend/src/components/ui/skeleton.jsx",
        "/app/frontend/src/components/ui/tooltip.jsx",
        "/app/frontend/src/components/ui/dialog.jsx",
        "/app/frontend/src/components/ui/select.jsx",
        "/app/frontend/src/components/ui/textarea.jsx",
        "/app/frontend/src/components/ui/input.jsx",
        "/app/frontend/src/components/ui/form.jsx",
        "/app/frontend/src/components/ui/progress.jsx",
        "/app/frontend/src/components/ui/collapsible.jsx"
      ],
      "icons": {
        "library": "lucide-react",
        "rule": "No emoji icons. Use lucide icons for status, database, clock, alert, check."
      },
      "toasts": {
        "library": "sonner",
        "component": "/app/frontend/src/components/ui/sonner.jsx"
      }
    },
    "key_ui_patterns": {
      "tables": {
        "schedule_table": {
          "requirements": [
            "Sticky header",
            "Row hover highlight",
            "Monospace numeric columns",
            "Right-aligned numeric cells",
            "Badges for day + location + cast availability"
          ],
          "classes": {
            "table": "text-sm",
            "th": "whitespace-nowrap text-xs uppercase tracking-wide text-muted-foreground",
            "td": "py-2",
            "numeric": "text-right font-mono tabular-nums"
          }
        },
        "clickhouse_evidence_table": {
          "identity": "Teal-accent header + database badge",
          "columns": [
            "Strategy",
            "Avg Cost",
            "Avg Delay",
            "Case Count"
          ],
          "classes": {
            "wrapper": "rounded-xl border border-[hsl(var(--cc-teal)/0.35)] bg-[hsl(var(--cc-teal)/0.06)]",
            "caption": "text-xs text-[hsl(var(--cc-teal))]"
          }
        },
        "decision_ledger_table": {
          "requirements": [
            "Dense audit feel",
            "Expandable row for evidence summary",
            "Copy decision id button"
          ]
        }
      },
      "agent_status_cards": {
        "layout": "6 cards in a 3x2 grid on desktop; 2x3 on medium; 1-column on mobile",
        "states": {
          "pending": {
            "badge": "bg-muted text-muted-foreground",
            "motion": "subtle shimmer skeleton"
          },
          "running": {
            "badge": "teal investigating badge",
            "motion": "pulse dot + progress bar indeterminate"
          },
          "complete": {
            "badge": "green badge",
            "motion": "check icon pop-in (scale 0.98→1)"
          }
        },
        "micro_interactions": [
          "Hover lifts card by 1px (shadow change only)",
          "On state change, animate badge background fade (150ms)"
        ]
      },
      "mcp_call_log_console": {
        "purpose": "Make ClickHouse querying visible on camera",
        "structure": [
          "Header: ‘Live MCP Call Log’ + connection badge + last updated time",
          "Rows: timestamp, tool, SQL preview, latency chip, rows returned chip, status",
          "Expandable row: full SQL in monospace block + copy button"
        ],
        "visual": {
          "container": "rounded-xl border bg-[hsl(var(--cc-panel-2))]",
          "sql_block": "font-mono text-xs leading-5 bg-black/30 border border-border rounded-lg p-3 overflow-auto",
          "chips": {
            "latency": "bg-muted text-foreground border-border font-mono",
            "rows": "bg-[hsl(var(--cc-teal)/0.14)] text-[hsl(var(--cc-teal))] border-[hsl(var(--cc-teal)/0.25)] font-mono"
          }
        }
      },
      "recovery_option_cards": {
        "count": "2–4",
        "recommended": {
          "treatment": "Gold outline + subtle gold glow shadow (not gradient)",
          "classes": "border-[hsl(var(--cc-gold)/0.55)] shadow-[0_0_0_1px_hsl(var(--cc-gold)/0.25),0_12px_40px_-24px_hsl(var(--cc-gold)/0.55)]"
        },
        "score_visual": {
          "pattern": "Weighted score as large mono number + mini bar (Progress)",
          "classes": "font-mono tabular-nums"
        },
        "approve_button": {
          "variant": "primary",
          "motion": "press scale 0.98, focus ring teal",
          "data_testid": "recovery-option-approve-button"
        }
      }
    }
  },
  "motion": {
    "library": {
      "recommended": "framer-motion",
      "why": "Smooth polling-driven transitions (agent states, option ranking, log row insertions)",
      "install": "npm i framer-motion"
    },
    "principles": [
      "No universal transition: never use transition-all",
      "Use 150–220ms for hover/focus, 280–420ms for panel entrance",
      "Prefer opacity + translateY(4px) for entrances",
      "Polling updates: animate new log rows with a brief highlight (teal tint)"
    ],
    "micro_interactions": {
      "buttons": "transition-colors duration-150 + active:scale-[0.98]",
      "table_rows": "hover:bg-muted/40",
      "badges": "state change crossfade (opacity)"
    }
  },
  "data_density_rules": {
    "alignment": [
      "All numeric columns right-aligned",
      "Use tabular-nums everywhere for money/hours",
      "Use consistent column widths for Day/Scene/Cost/Delay"
    ],
    "formatting": {
      "money": "$12,450 (mono)",
      "delay": "6.5h (mono)",
      "risk": "Low/Med/High badge"
    }
  },
  "accessibility": {
    "requirements": [
      "WCAG AA contrast for text on dark surfaces",
      "Visible focus ring (ring color uses --ring teal)",
      "Reduced motion support: respect prefers-reduced-motion (disable pulsing/shimmer)",
      "Tooltips for truncated SQL and long labels"
    ],
    "keyboard": [
      "Sidebar nav items focusable",
      "Tables: row actions reachable via Tab",
      "Dialog/Sheet uses shadcn primitives"
    ]
  },
  "testing_attributes": {
    "rule": "All interactive and key informational elements MUST include data-testid (kebab-case).",
    "examples": [
      "data-testid=\"sidebar-nav-production-dashboard\"",
      "data-testid=\"report-disruption-submit-button\"",
      "data-testid=\"agent-status-orchestrator-card\"",
      "data-testid=\"mcp-call-log-row\"",
      "data-testid=\"clickhouse-evidence-table\"",
      "data-testid=\"decision-ledger-table\""
    ]
  },
  "image_urls": {
    "hero_or_header_background_optional": [
      {
        "url": "https://images.unsplash.com/photo-1562184525-ead42cf98b1e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwzfHxjaW5lbWF0aWMlMjBmaWxtJTIwcHJvZHVjdGlvbiUyMGNvbnRyb2wlMjByb29tJTIwZGFzaGJvYXJkfGVufDB8fHxibGFja3wxNzg3MDczMjY2fDA&ixlib=rb-4.1.0&q=85",
        "category": "decorative",
        "description": "Abstract monitor wall / control room vibe. Use as very subtle blurred background in header strip only (opacity 0.06–0.10)."
      }
    ],
    "empty_state_or_side_panel": [
      {
        "url": "https://images.pexels.com/photos/6253568/pexels-photo-6253568.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "category": "decorative",
        "description": "Editing timeline close-up. Use in empty state card for ‘No disruptions yet’ (cropped, grayscale, opacity 0.12)."
      }
    ]
  },
  "instructions_to_main_agent": {
    "global": [
      "Set dark mode by default by applying className=\"dark\" on the root html/body wrapper (CRA).",
      "Replace CRA default App.css centering styles; do NOT center the app container.",
      "Update /app/frontend/src/index.css tokens to the cinematic palette above.",
      "Use Space Grotesk + Inter + IBM Plex Mono via Google Fonts (index.html link tags).",
      "Use shadcn Table/Card/Badge for Recovery Options + Decision Ledger; keep tables crisp and aligned.",
      "Make ClickHouse evidence visually distinct (teal identity) and always labeled ‘Historical Evidence (ClickHouse)’.",
      "No websockets: simulate liveness with polling + skeletons + animated state transitions.",
      "Every interactive element and key info must include data-testid (kebab-case)."
    ],
    "page_specific": {
      "agent_investigation": [
        "Show 6 agent cards with states pending/running/complete.",
        "Below, render Live MCP Call Log with SQL preview + latency + rows returned.",
        "Use Collapsible for expandable SQL details; include Copy button."
      ],
      "recovery_options": [
        "Left: option cards (2–4) with rank + recommended highlight.",
        "Right: ClickHouse evidence table with teal border/background.",
        "Make cost/delay visually striking: large mono numerals + right-aligned metrics."
      ]
    },
    "js_files_note": "Project uses .js/.jsx. Write components accordingly (no .tsx types)."
  },
  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
