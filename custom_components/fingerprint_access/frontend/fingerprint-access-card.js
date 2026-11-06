/* Fingerprint Access dashboard card — permissions are enforced server-side. */
class FingerprintAccessCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._editing = null;
    this._busy = false;
    this._noticeText = "";
  }
  setConfig(config) {
    if (typeof config?.entity !== "string" || !config.entity.startsWith("sensor.")) {
      throw new Error("Select the Fingerprint Access 'Registered fingerprints' sensor");
    }
    this._config = config;
    this._render();
  }
  static getStubConfig(hass) {
    // The assigned HA entity ID depends on the language, installation and
    // collision handling. Discover the correct registry sensor automatically.
    const matched = Object.entries(hass?.states || {}).find(([entityId, state]) =>
      entityId.startsWith("sensor.") &&
      typeof state.attributes?.entry_id === "string" &&
      typeof state.attributes?.reader === "string" &&
      Array.isArray(state.attributes?.people)
    );
    return {entity: matched?.[0] || "sensor.registered_fingerprints"};
  }
  getCardSize() { return 7; }
  set hass(value) {
    const before = this._hass?.states[this._config?.entity];
    const oldAdmin = this._hass?.user?.is_admin;
    this._hass = value;
    if (before !== value.states[this._config?.entity] || oldAdmin !== value.user?.is_admin) this._render();
  }
  _el(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = String(text);
    if (cls) el.className = cls;
    return el;
  }
  _button(text, callback, kind = "") {
    const b = this._el("button", text, kind);
    b.type = "button";
    b.disabled = this._busy;
    b.onclick = callback;
    return b;
  }
  _select(profile) {
    const sel = this._el("select");
    for (const [value, label] of [["partial", "Accesso parziale"], ["full", "Accesso completo"]]) {
      const opt = this._el("option", label);
      opt.value = value;
      sel.append(opt);
    }
    sel.value = profile;
    return sel;
  }
  async _action(name, data, successMessage) {
    if (this._busy || !this._hass?.user?.is_admin) return;
    this._busy = true;
    try {
      await this._hass.callService("fingerprint_access", name, data);
      this._noticeText = successMessage;
      this._editing = null;
    } catch (error) {
      this._noticeText = "Errore: " + (error?.message || String(error));
    } finally {
      this._busy = false;
      this._render();
    }
  }
  _render() {
    if (!this._hass || !this._config) return;
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = this._el("style");
    style.textContent = [
      ":host{display:block}ha-card{display:block;padding:20px;color:var(--primary-text-color)}",
      "h2{margin:0 0 10px;font-size:20px}h3{margin:24px 0 10px;font-size:16px}",
      ".meta{color:var(--secondary-text-color);font-size:13px}.warn{color:var(--error-color,#b71c1c)}",
      ".line{margin:8px 0}.note{padding:10px;background:var(--secondary-background-color,#eee);border-radius:8px}",
      "table{border-collapse:collapse;width:100%}td,th{padding:9px 6px;text-align:left;border-bottom:1px solid var(--divider-color,#ddd)}",
      ".scroll{overflow:auto}button,input,select{font:inherit;border-radius:7px;padding:8px;border:1px solid var(--divider-color,#aaa)}",
      "button{cursor:pointer;background:var(--secondary-background-color,#eee);color:var(--primary-text-color);margin:2px}",
      "button:disabled{opacity:.55}input,select{color:var(--primary-text-color);background:var(--card-background-color,white);max-width:100%;box-sizing:border-box}",
      ".buttons{display:flex;flex-wrap:wrap;align-items:center}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:12px}",
      "label{display:flex;flex-direction:column;gap:6px;font-size:13px}.danger{color:var(--error-color,#b71c1c)}"
    ].join("");
    root.append(style);
    const card = this._el("ha-card");
    root.append(card);
    card.append(this._el("h2", "Fingerprint Access"));
    const state = this._hass.states[this._config.entity];
    if (!state) {
      card.append(this._el("p", "Sensore non trovato: verifica l'ID entity nella configurazione della scheda.", "warn"));
      return;
    }
    const attrs = state.attributes || {};
    const entry_id = attrs.entry_id;
    const people = Array.isArray(attrs.people) ? attrs.people : [];
    const admin = !!this._hass.user?.is_admin;
    card.append(this._el("p", "Lettore: " + (attrs.reader || "—") + " · " + people.length + " identità", "meta"));
    card.append(this._el("p", attrs.test_mode ? "MODALITÀ TEST: le azioni NON vengono eseguite." : "ATTENZIONE: le azioni sono attive.", attrs.test_mode ? "note" : "warn"));
    if (this._noticeText) card.append(this._el("p", this._noticeText, "note"));
    if (attrs.last_scan?.status) {
      card.append(this._el("p", "Ultimo evento: " + attrs.last_scan.status + (attrs.last_scan.slot == null ? "" : " · ID " + attrs.last_scan.slot), "meta"));
    }
    if (attrs.pending_enrollment != null) {
      const row = this._el("div", null, "buttons");
      row.append(this._el("span", "Registrazione in corso: ID " + attrs.pending_enrollment));
      if (admin) row.append(this._button("Annulla registrazione", () => {
        if (window.confirm("Annullare la registrazione corrente?")) {
          void this._action("cancel_enrollment", {entry_id}, "Richiesta di annullamento inviata.");
        }
      }));
      card.append(row);
    }
    card.append(this._el("h3", "Rubrica"));
    const scroll = this._el("div", null, "scroll");
    const table = this._el("table");
    const header = this._el("tr");
    for (const name of ["ID", "Nome", "Profilo", ...(admin ? ["Amministrazione"] : [])]) {
      header.append(this._el("th", name));
    }
    table.append(header);
    for (const p of [...people].sort((a,b) => Number(a.finger_id)-Number(b.finger_id))) {
      const id = Number(p.finger_id);
      const row = this._el("tr");
      row.append(this._el("td", id));
      if (admin && this._editing === id) {
        const nameCell = this._el("td"), profileCell = this._el("td"), actionsCell = this._el("td");
        const nameInput = this._el("input");
        nameInput.value = p.name || "";
        nameInput.maxLength = 80;
        const profileInput = this._select(p.profile);
        nameCell.append(nameInput);
        profileCell.append(profileInput);
        actionsCell.append(this._button("Salva", () => {
          const name = nameInput.value.trim(), profile = profileInput.value;
          if (!name || name.length > 80) return window.alert("Nome non valido.");
          if (!window.confirm("Confermi l'ID " + id + " (" + name + ") con profilo " + (profile === "full" ? "COMPLETO" : "PARZIALE") + "?")) return;
          void this._action("update_person", {entry_id, finger_id: id, name, profile}, "ID " + id + " aggiornato.");
        }));
        actionsCell.append(this._button("Annulla", () => {this._editing=null;this._render();}));
        row.append(nameCell, profileCell, actionsCell);
      } else {
        row.append(this._el("td", p.name || "—"));
        row.append(this._el("td", p.profile === "full" ? "Accesso completo" : p.profile === "partial" ? "Accesso parziale" : "Non valido"));
        if (admin) {
          const cell = this._el("td", null, "buttons");
          cell.append(this._button("Modifica", () => {this._editing=id;this._render();}));
          cell.append(this._button("Elimina", () => {
            const typed = window.prompt("Revoca e cancellazione irreversibile dell'ID " + id + ".\nDigita l'ID per confermare:");
            if (typed !== String(id)) return;
            void this._action("delete_person", {entry_id, finger_id:id}, "ID " + id + " revocato; cancellazione dal lettore richiesta.");
          }, "danger"));
          row.append(cell);
        }
      }
      table.append(row);
    }
    if (!people.length) {
      const tr = this._el("tr"), td = this._el("td", "Nessuna persona autorizzata.");
      td.colSpan = admin ? 4 : 3;
      tr.append(td);
      table.append(tr);
    }
    scroll.append(table);
    card.append(scroll);
    if (!admin) {
      card.append(this._el("p", "Per modifiche e registrazioni è necessario un account amministratore.", "meta"));
      return;
    }
    card.append(this._el("h3", "Registra impronta"));
    card.append(this._el("p", "Verifica che lo slot sia fisicamente vuoto. Il permesso viene salvato soltanto dopo l'evento di registrazione completata.", "meta"));
    const form = this._el("form"), fields = this._el("div", null, "fields");
    const maxUsed = people.reduce((m,p) => Math.max(m,Number(p.finger_id)||0),0);
    const slotLabel = this._el("label", "ID slot (suggerito, non verificato)");
    const slot = this._el("input"); slot.type="number";slot.min="1";slot.max="199";slot.step="1";slot.value=String(Math.min(199,maxUsed+1));slot.required=true;
    slotLabel.append(slot);
    const nameLabel = this._el("label", "Nome");
    const name = this._el("input");name.maxLength=80;name.required=true;nameLabel.append(name);
    const profileLabel = this._el("label", "Profilo");
    const profile = this._select("partial");profileLabel.append(profile);
    const scansLabel = this._el("label", "Scansioni");
    const scans = this._el("input");scans.type="number";scans.min="2";scans.max="6";scans.step="1";scans.value="2";scansLabel.append(scans);
    fields.append(slotLabel,nameLabel,profileLabel,scansLabel);
    form.append(fields);
    const submit = this._el("button","Avvia registrazione");
    submit.type="submit";
    submit.disabled = this._busy || attrs.pending_enrollment != null;
    form.append(submit);
    form.onsubmit = ev => {
      ev.preventDefault();
      const finger_id=Number(slot.value), num_scans=Number(scans.value), person=name.value.trim(), selected=profile.value;
      if(!Number.isInteger(finger_id)||finger_id<1||finger_id>199||people.some(p=>Number(p.finger_id)===finger_id)) return window.alert("ID non valido o già registrato in rubrica.");
      if(!person||person.length>80||!Number.isInteger(num_scans)||num_scans<2||num_scans>6) return window.alert("Controlla nome e scansioni.");
      if(!window.confirm("Hai verificato FISICAMENTE che l'ID " + finger_id + " sia libero?\nRegistra " + person + " con profilo " + (selected==="full"?"COMPLETO":"PARZIALE") + "?")) return;
      void this._action("enroll",{entry_id,finger_id,name:person,profile:selected,num_scans,confirm_free_slot:true},"Registrazione ID " + finger_id + " avviata: attendi il completamento sul lettore.");
    };
    card.append(form);
  }
}
if (!customElements.get("fingerprint-access-card")) customElements.define("fingerprint-access-card", FingerprintAccessCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(card=>card.type==="fingerprint-access-card")) window.customCards.push({
  type:"fingerprint-access-card",name:"Fingerprint Access",description:"Rubrica e registrazione impronte ESPHome",preview:false,
  documentationURL:"https://github.com/paolofaz/ha-fingerprint-access"
});
