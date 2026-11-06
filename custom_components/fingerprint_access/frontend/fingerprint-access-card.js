/* Fingerprint Access – responsive Lovelace card, Release Candidate.
   The backend, not the card, enforces all access permissions. */
class FingerprintAccessCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._hass = null;
    this._config = null;
    this._busy = false;
    this._error = false;
    this._message = "";
    this._editing = null;
    this._edit = null;
    this._draft = {slot: "", name: "", profile: "partial", scans: "2"};
  }

  static getStubConfig(hass) {
    const match = Object.entries(hass?.states || {}).find(([id, state]) =>
      id.startsWith("sensor.") &&
      typeof state.attributes?.reader === "string" &&
      typeof state.attributes?.entry_id === "string" &&
      Array.isArray(state.attributes?.people));
    return {entity: match?.[0] || "sensor.registered_fingerprints"};
  }
  getCardSize() { return 7; }

  setConfig(config) {
    if (!config || typeof config.entity !== "string" ||
        !config.entity.startsWith("sensor.")) {
      throw new Error("Select the Fingerprint Access registered fingerprints sensor");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const priorState = this._hass?.states[this._config?.entity];
    const priorAdmin = !!this._hass?.user?.is_admin;
    this._hass = hass;
    if (priorState !== hass.states[this._config?.entity] ||
        priorAdmin !== !!hass.user?.is_admin) this._render();
  }

  _el(tag, txt = null, cls = "") {
    const node = document.createElement(tag);
    if (txt !== null) node.textContent = String(txt);
    if (cls) node.className = cls;
    return node;
  }

  _button(label, callback, className = "") {
    const b = this._el("button", label, className);
    b.type = "button";
    b.disabled = this._busy;
    b.addEventListener("click", callback);
    return b;
  }

  _field(label, type, value, onInput) {
    const wrap = this._el("label", null, "field");
    wrap.append(this._el("span", label));
    const input = this._el("input");
    input.type = type;
    input.value = String(value ?? "");
    input.oninput = () => onInput(input.value);
    wrap.append(input);
    return {wrap, input};
  }

  _select(current, callback) {
    const sel = this._el("select");
    for (const [value, label] of [
      ["partial", "Accesso parziale"],
      ["full", "Accesso completo"]
    ]) {
      const option = this._el("option", label);
      option.value = value;
      sel.append(option);
    }
    sel.value = current;
    sel.onchange = () => callback(sel.value);
    return sel;
  }

  _date(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return "—";
    return date.toLocaleTimeString("it-IT", {
      hour: "2-digit", minute: "2-digit", second: "2-digit"
    });
  }

  _status(code) {
    return {
      denied: "Impronta non autorizzata",
      invalid_id: "ID non valido",
      user_event_ignored: "Evento manuale ignorato",
      blocked_during_enrollment: "Lettura sospesa durante registrazione",
      busy_ignored: "Lettura ravvicinata ignorata",
      cooldown_ignored: "Pausa di sicurezza tra aperture",
      post_enrollment_ignored: "Attendi dopo la registrazione",
      no_actions_configured: "Nessuna azione configurata",
      action_started: "Apertura avviata: sequenza in esecuzione",
      action_executed: "Sequenza azioni completata",
      action_failed: "Errore durante le azioni",
      enrollment_started: "Registrazione avviata",
      enrolling_scan: "Scansione di registrazione",
      enrollment_saved: "Impronta registrata e autorizzata",
      enrollment_failed: "Registrazione fallita",
      enrollment_timeout: "Tempo di registrazione scaduto",
      enrollment_start_failed: "Impossibile avviare la registrazione",
      enrollment_save_failed: "Errore nel salvataggio (accesso negato)",
      enrollment_cancelled: "Registrazione annullata",
      enrollment_cancel_failed: "Impossibile annullare sul lettore",
      person_updated: "Persona aggiornata",
      access_revoked: "Accesso revocato",
      template_delete_requested: "Cancellazione richiesta al lettore",
      unexpected_enrollment_done: "Esito di registrazione inatteso"
    }[code] || (code || "—");
  }

  async _call(service, data, successText) {
    if (this._busy || !this._hass?.user?.is_admin) return;
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("fingerprint_access", service, data);
      this._message = successText;
      this._error = false;
      this._editing = null;
      this._edit = null;
      if (service === "enroll") {
        this._draft.name = "";
      }
    } catch (error) {
      this._message = error?.message || String(error);
      this._error = true;
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _render() {
    if (!this._config || !this._hass) return;
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = this._el("style");
    style.textContent = [
      ":host{display:block}*{box-sizing:border-box}ha-card{display:block;color:var(--primary-text-color);padding:20px}",
      "h2{font-size:20px;line-height:1.3;margin:0}h3{font-size:16px;margin:0}",
      ".header,.meta-line,.person,.buttons,.statusrow,.footer{display:flex;align-items:center;gap:10px}",
      ".header{justify-content:space-between;flex-wrap:wrap}.muted{color:var(--secondary-text-color);font-size:13px}",
      ".pill{border:1px solid var(--divider-color,#ddd);border-radius:20px;padding:5px 10px;font-size:12px}",
      ".pill.full{color:var(--primary-color,#1976d2)}.pill.partial{color:var(--secondary-text-color)}",
      ".count{font-variant-numeric:tabular-nums;font-weight:600}.section{margin-top:20px;border-top:1px solid var(--divider-color,#ddd);padding-top:18px}",
      ".status{border-radius:12px;background:var(--secondary-background-color,#f4f6f8);padding:13px;margin-top:16px}",
      ".statusrow{justify-content:space-between;align-items:center}.status-title{font-weight:600}.status-time{white-space:nowrap;font-size:12px;color:var(--secondary-text-color)}",
      ".status-detail{color:var(--secondary-text-color);margin-top:4px;font-size:13px}",
      ".list{display:grid;gap:8px;margin-top:12px}.person{justify-content:space-between;border:1px solid var(--divider-color,#ddd);border-radius:12px;padding:12px;flex-wrap:wrap}",
      ".identity{min-width:0;flex:1}.name{font-weight:600;overflow-wrap:anywhere}.subtitle{font-size:12px;color:var(--secondary-text-color);margin-top:3px}",
      ".slot{border-radius:8px;background:var(--secondary-background-color,#f4f6f8);padding:8px 12px;font-weight:700;font-variant-numeric:tabular-nums}",
      ".buttons{flex-wrap:wrap}.note{border-radius:9px;padding:10px;background:var(--secondary-background-color,#f4f6f8);font-size:13px;margin-top:12px}",
      ".error{color:var(--error-color,#d32f2f)}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}",
      ".field{display:flex;flex-direction:column;gap:5px;font-size:13px;min-width:0}",
      "input,select,button{font:inherit;border:1px solid var(--divider-color,#aaa);border-radius:9px;padding:10px;max-width:100%}",
      "input,select{width:100%;min-width:0;background:var(--card-background-color,white);color:var(--primary-text-color)}",
      "button{background:var(--secondary-background-color,#eee);color:var(--primary-text-color);cursor:pointer}",
      "button.primary{background:var(--primary-color,#1976d2);border-color:var(--primary-color,#1976d2);color:#fff}",
      "button.danger{color:var(--error-color,#d32f2f)}button:disabled{opacity:.5;cursor:not-allowed}",
      ".footer{justify-content:space-between;flex-wrap:wrap;margin-top:15px}",
      "details{margin-top:16px}summary{cursor:pointer;font-weight:600}details .note{margin-top:8px}",
      "@media(max-width:550px){ha-card{padding:16px}.fields{grid-template-columns:1fr}.person{align-items:flex-start}.buttons{width:100%;justify-content:flex-end}.statusrow{align-items:flex-start}}"
    ].join("");
    root.append(style);

    const card = this._el("ha-card");
    root.append(card);
    const header = this._el("div", null, "header");
    header.append(this._el("h2", "Fingerprint Access"));
    const state = this._hass.states[this._config.entity];
    if (!state) {
      card.append(header, this._el("p", "Sensore non trovato: verifica l'entità della rubrica.", "error"));
      return;
    }
    const a = state.attributes || {};
    const admin = !!this._hass.user?.is_admin;
    const people = Array.isArray(a.people) ? a.people : [];
    header.append(this._el("span", people.length + " impronte", "pill count"));
    card.append(header);
    card.append(this._el("div", "Lettore: " + (a.reader || "—"), "muted"));

    if (this._message) card.append(this._el("div", this._message, "note" + (this._error ? " error" : "")));
    if (!a.full_actions_configured || !a.partial_actions_configured) {
      card.append(this._el("div", "Verifica le azioni dei due profili nelle impostazioni dell'integrazione: almeno una sequenza non è configurata.", "note"));
    }

    const last = a.last_scan || {};
    if (last.status) {
      const wrap = this._el("div", null, "status");
      const line = this._el("div", null, "statusrow");
      line.append(this._el("span", this._status(last.status), "status-title"));
      line.append(this._el("span", this._date(last.when), "status-time"));
      wrap.append(line);
      const fragments = [];
      if (last.slot != null) fragments.push("ID " + last.slot);
      if (last.name) fragments.push(last.name);
      if (last.profile) fragments.push(last.profile === "full" ? "Accesso completo" : "Accesso parziale");
      if (last.matched_count != null) fragments.push("Letture dall'avvio: " + last.matched_count);
      if (fragments.length) wrap.append(this._el("div", fragments.join(" · "), "status-detail"));
      card.append(wrap);
    }

    if (a.pending_enrollment !== null && a.pending_enrollment !== undefined) {
      const pending = this._el("div", "Registrazione in corso: ID " + a.pending_enrollment, "note");
      if (admin) pending.append(this._button("Annulla", () => {
        if (window.confirm("Vuoi annullare la registrazione?")) {
          void this._call("cancel_enrollment", {entry_id:a.entry_id}, "Annullamento richiesto.");
        }
      }));
      card.append(pending);
    }

    const sec = this._el("section", null, "section");
    sec.append(this._el("h3", "Rubrica"));
    card.append(sec);
    const list = this._el("div", null, "list");
    sec.append(list);
    if (!people.length) list.append(this._el("div", "Nessuna impronta autorizzata.", "muted"));

    const sorted = [...people].sort((x,y) => Number(x.finger_id)-Number(y.finger_id));
    for (const p of sorted) {
      const id = Number(p.finger_id);
      const person = this._el("article", null, "person");
      person.append(this._el("div", id, "slot"));

      if (admin && this._editing === id) {
        const editor = this._el("div", null, "identity");
        const n = this._field("Nome", "text", this._edit?.name ?? p.name, value => {this._edit.name=value;});
        n.input.maxLength = 80;
        const choice = this._select(this._edit?.profile || p.profile, value => {this._edit.profile=value;});
        const cp = this._el("label", null, "field");
        cp.append(this._el("span","Profilo"),choice);
        editor.append(n.wrap,cp);
        person.append(editor);
        const buttons = this._el("div", null, "buttons");
        buttons.append(this._button("Salva", () => {
          const name=(this._edit?.name||"").trim(), profile=this._edit?.profile;
          if (!name || name.length>80) return window.alert("Inserisci un nome valido.");
          const change = profile !== p.profile ? "\nATTENZIONE: cambia i permessi di accesso." : "";
          if (window.confirm("Salvare ID " + id + " — " + name + " — " + (profile==="full"?"COMPLETO":"PARZIALE") + "?"+change)) {
            void this._call("update_person", {entry_id:a.entry_id,finger_id:id,name,profile}, "Identità aggiornata.");
          }
        },"primary"));
        buttons.append(this._button("Annulla",() => {this._editing=null;this._edit=null;this._render();}));
        person.append(buttons);
      } else {
        const name = this._el("div", null, "identity");
        name.append(this._el("div", p.name || "—", "name"));
        name.append(this._el("div", p.profile === "full" ? "Accesso completo" : "Accesso parziale", "subtitle"));
        person.append(name);
        if (admin) {
          const actions = this._el("div", null, "buttons");
          actions.append(this._button("Modifica", () => {
            this._editing=id;this._edit={name:p.name||"",profile:p.profile};this._render();
          }));
          actions.append(this._button("Elimina", () => {
            const typed=window.prompt("Revoca ID "+id+" ed elimina il modello biometrico.\nScrivi l'ID esatto per confermare:");
            if(typed!==String(id))return;
            if(!window.confirm("Confermi la revoca di "+(p.name||"ID "+id)+"? Non è reversibile."))return;
            void this._call("delete_person",{entry_id:a.entry_id,finger_id:id},"Revoca salvata; cancellazione richiesta al lettore.");
          },"danger"));
          person.append(actions);
        }
      }
      list.append(person);
    }

    if (admin) {
      const formSection=this._el("section",null,"section");
      card.append(formSection);
      formSection.append(this._el("h3","Registra nuova impronta"));
      formSection.append(this._el("p","Scegli ID, nome e accesso. L'autorizzazione viene salvata solo dopo la registrazione riuscita.","muted"));
      const form=this._el("form");
      const fields=this._el("div",null,"fields");
      const used=new Set(people.map(p=>Number(p.finger_id)));
      let suggested=1;while(used.has(suggested)&&suggested<199)suggested++;
      if(!this._draft.slot || used.has(Number(this._draft.slot))) {
        this._draft.slot=String(suggested);
      }
      const slot=this._field("ID slot (da verificare sul lettore)","number",this._draft.slot,value=>{this._draft.slot=value;});
      slot.input.min="1";slot.input.max="199";slot.input.step="1";slot.input.required=true;
      const name=this._field("Nome","text",this._draft.name,value=>{this._draft.name=value;});
      name.input.required=true;name.input.maxLength=80;
      const selectLabel=this._el("label",null,"field");
      selectLabel.append(this._el("span","Profilo"));
      const profile=this._select(this._draft.profile,value=>{this._draft.profile=value;});
      selectLabel.append(profile);
      const scans=this._field("Numero scansioni","number",this._draft.scans,value=>{this._draft.scans=value;});
      scans.input.min="2";scans.input.max="6";scans.input.step="1";scans.input.required=true;
      fields.append(slot.wrap,name.wrap,selectLabel,scans.wrap);
      form.append(fields);
      const footer=this._el("div",null,"footer");
      const submit=this._el("button","Avvia registrazione","primary");
      submit.type="submit";submit.disabled=this._busy||a.pending_enrollment!=null;
      footer.append(submit);
      form.append(footer);
      form.onsubmit=event=>{
        event.preventDefault();
        const finger_id=Number(this._draft.slot);
        const num_scans=Number(this._draft.scans);
        const personName=this._draft.name.trim();
        const selected=this._draft.profile;
        if(!Number.isInteger(finger_id)||finger_id<1||finger_id>199||used.has(finger_id))return window.alert("ID non valido o già in rubrica.");
        if(!Number.isInteger(num_scans)||num_scans<2||num_scans>6||!personName||personName.length>80)return window.alert("Controlla il nome e il numero di scansioni.");
        if(!window.confirm("Hai verificato che lo slot "+finger_id+" sia LIBERO sul lettore?\n\nPersona: "+personName+"\nAutorizzazione: "+(selected==="full"?"COMPLETA":"PARZIALE")+"\n\nProcedere?"))return;
        void this._call("enroll",{entry_id:a.entry_id,finger_id,name:personName,profile:selected,num_scans,confirm_free_slot:true},"Registrazione avviata. Segui il LED del lettore.");
      };
      formSection.append(form);
    }

    const recent=Array.isArray(a.recent_events)?a.recent_events:[];
    if(recent.length) {
      const section=this._el("details");
      const summary=this._el("summary","Ultimi eventi ("+recent.length+")");
      section.append(summary);
      for(const e of recent) {
        section.append(this._el("div",this._date(e.when)+" · "+(e.slot==null?"—":"ID "+e.slot)+" · "+this._status(e.status),"line muted"));
      }
      card.append(section);
    }
  }
}
if (!customElements.get("fingerprint-access-card")) {
  customElements.define("fingerprint-access-card",FingerprintAccessCard);
}
window.customCards=window.customCards||[];
if (!window.customCards.some(c=>c.type==="fingerprint-access-card")) {
  window.customCards.push({
    type:"fingerprint-access-card",
    name:"Fingerprint Access",
    description:"Rubrica e gestione impronte ESPHome",
    preview:false,
    documentationURL:"https://github.com/paolofaz/ha-fingerprint-access"
  });
}
