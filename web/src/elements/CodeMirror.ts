import { EVENT_THEME_CHANGE } from "#common/constants";

import { AKElement } from "#elements/Base";

import { UiThemeEnum } from "@goauthentik/api";

import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { css as cssLang } from "@codemirror/lang-css";
import { html as htmlLang } from "@codemirror/lang-html";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { xml } from "@codemirror/lang-xml";
import {
    defaultHighlightStyle,
    LanguageSupport,
    StreamLanguage,
    syntaxHighlighting,
} from "@codemirror/language";
import * as yamlMode from "@codemirror/legacy-modes/mode/yaml";
import { Compartment, EditorState, Extension } from "@codemirror/state";
import { oneDark, oneDarkHighlightStyle } from "@codemirror/theme-one-dark";
import { drawSelection, EditorView, keymap, lineNumbers, ViewUpdate } from "@codemirror/view";
import YAML from "yaml";

import { css, CSSResult } from "lit";
import { customElement, property } from "lit/decorators.js";

export enum CodeMirrorMode {
    XML = "xml",
    JavaScript = "javascript",
    HTML = "html",
    CSS = "css",
    Python = "python",
    YAML = "yaml",
}

@customElement("ak-codemirror")
export class CodeMirrorTextarea<T> extends AKElement {
    @property({ type: Boolean })
    readOnly = false;

    @property()
    mode: CodeMirrorMode = CodeMirrorMode.YAML;

    @property()
    name?: string;

    @property({ type: Boolean })
    parseValue = true;

    editor?: EditorView;

    _value?: string;

    theme: Compartment = new Compartment();
    syntaxHighlighting: Compartment = new Compartment();

    themeLight = EditorView.theme(
        {
            "&": {
                backgroundColor: "var(--pf-global--BackgroundColor--light-300)",
            },
        },
        { dark: false },
    );
    themeDark = oneDark;
    syntaxHighlightingLight = syntaxHighlighting(defaultHighlightStyle);
    syntaxHighlightingDark = syntaxHighlighting(oneDarkHighlightStyle);

    static styles: CSSResult[] = [
        // Better alignment with patternfly components
        css`
            .cm-editor {
                padding-top: calc(
                    var(--pf-global--spacer--form-element) - var(--pf-global--BorderWidth--sm)
                );
                padding-bottom: calc(
                    var(--pf-global--spacer--form-element) - var(--pf-global--BorderWidth--sm)
                );
                padding-right: var(--pf-c-form-control--inset--base);
                padding-left: var(--pf-c-form-control--inset--base);
            }
        `,
    ];

    @property()
    set value(v: T | string) {
        if (v === null || v === undefined) {
            return;
        }
        // Value might be an object if within an iron-form, as that calls the getter of value
        // in the beginning and the calls this setter on reset
        let textValue = v;
        if (!(typeof v === "string" || v instanceof String)) {
            switch (this.mode.toLowerCase()) {
                case "yaml":
                    textValue = YAML.stringify(v);
                    break;
                case "javascript":
                    textValue = JSON.stringify(v);
                    break;
                default:
                    textValue = v.toString();
                    break;
            }
        }
        if (this.editor) {
            this.editor.dispatch({
                changes: { from: 0, to: this.editor.state.doc.length, insert: textValue as string },
            });
        } else {
            this._value = textValue as string;
        }
    }

    get value(): T | string {
        if (!this.parseValue) {
            return this.getInnerValue();
        }
        try {
            switch (this.mode) {
                case CodeMirrorMode.YAML:
                    return YAML.parse(this.getInnerValue());
                case CodeMirrorMode.JavaScript:
                    return JSON.parse(this.getInnerValue());
                default:
                    return this.getInnerValue();
            }
        } catch (_e: unknown) {
            return this.getInnerValue();
        }
    }

    private getInnerValue(): string {
        if (!this.editor) {
            return "";
        }
        return this.editor.state.doc.toString();
    }

    getLanguageExtension(): LanguageSupport | undefined {
        switch (this.mode.toLowerCase()) {
            case CodeMirrorMode.XML:
                return xml();
            case CodeMirrorMode.JavaScript:
                return javascript();
            case CodeMirrorMode.HTML:
                return htmlLang();
            case CodeMirrorMode.Python:
                return python();
            case CodeMirrorMode.CSS:
                return cssLang();
            case CodeMirrorMode.YAML:
                return new LanguageSupport(StreamLanguage.define(yamlMode.yaml));
        }
        return undefined;
    }

    firstUpdated(): void {
        this.addEventListener(EVENT_THEME_CHANGE, ((ev: CustomEvent<UiThemeEnum>) => {
            if (ev.detail === UiThemeEnum.Dark) {
                this.editor?.dispatch({
                    effects: [
                        this.theme.reconfigure(this.themeDark),
                        this.syntaxHighlighting.reconfigure(this.syntaxHighlightingDark),
                    ],
                });
            } else {
                this.editor?.dispatch({
                    effects: [
                        this.theme.reconfigure(this.themeLight),
                        this.syntaxHighlighting.reconfigure(this.syntaxHighlightingLight),
                    ],
                });
            }
        }) as EventListener);

        const dark = this.activeTheme === UiThemeEnum.Dark;

        const extensions = [
            history(),
            keymap.of([...defaultKeymap, ...historyKeymap]),
            this.getLanguageExtension(),
            lineNumbers(),
            drawSelection(),
            EditorView.lineWrapping,
            EditorView.updateListener.of((v: ViewUpdate) => {
                if (!v.docChanged) {
                    return;
                }
                this.dispatchEvent(
                    new CustomEvent("change", {
                        detail: v,
                    }),
                );
            }),
            EditorState.readOnly.of(this.readOnly),
            EditorState.tabSize.of(2),
            this.syntaxHighlighting.of(
                dark ? this.syntaxHighlightingDark : this.syntaxHighlightingLight,
            ),
            this.theme.of(dark ? this.themeDark : this.themeLight),
        ];
        this.editor = new EditorView({
            extensions: extensions.filter((p) => p) as Extension[],
            root: this.shadowRoot || document,
            doc: this._value,
        });
        this.shadowRoot?.appendChild(this.editor.dom);
    }
}

declare global {
    interface HTMLElementTagNameMap {
        "ak-codemirror": CodeMirrorTextarea<unknown>;
    }
}
