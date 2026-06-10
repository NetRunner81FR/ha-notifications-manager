const VERSION = "0.9.0";

const SETTINGS_ALLOWLIST =
  /^(switch\.notif_[a-z0-9_]+_(email_enabled|push_enabled|role_(admin|proprietaire|resident|utilisateur))|switch\.notifications_manager_smtp_active)$/;
const PUSH_TARGET_ALLOWLIST = /^text\.notif_[a-z0-9_]+_push_target$/;
const EMAIL_ALLOWLIST = /^text\.notif_[a-z0-9_]+_email$/;
const PKG_ADMIN_ALLOWLIST = /^input_boolean\.[a-z0-9_]+_notif_admin$/;
const PKG_LEVEL_ALLOWLIST = /^input_select\.[a-z0-9_]+_notification_level$/;

const TABS = [
  { id: "supervision", label: "Supervision" },
  { id: "modules", label: "Modules" },
  { id: "users", label: "Utilisateurs" },
  { id: "settings", label: "Paramètres" },
  { id: "audit", label: "Audit" },
];

class NotificationsSupervisionPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._activeTab = "supervision";
    this._addExpanded = null;
    this._addForm = {};
    this._removeConfirm = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set panel(_panel) {}

  set narrow(narrow) {
    this._narrow = narrow;
  }

  // ── Render principal ─────────────────────────────────────────────────────────

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const tabsHtml = TABS.map(
      (t) =>
        `<button class="tab${this._activeTab === t.id ? " active" : ""}" data-tab="${t.id}">${t.label}</button>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <div class="panel">
        <div class="panel-nav">
          <button class="nav-btn" data-nav="/dashboard-apercu/accueil-maison">
            <ha-icon icon="mdi:home-outline"></ha-icon>
            <span>Accueil</span>
          </button>
          <button class="nav-btn" data-nav="/dashboard-notifications-v2/supervision-v2">
            <ha-icon icon="mdi:bell-outline"></ha-icon>
            <span>Supervision</span>
          </button>
          <button class="nav-btn" data-nav="/dashboard-admin/admin">
            <ha-icon icon="mdi:cog-outline"></ha-icon>
            <span>Admin</span>
          </button>
        </div>
        <div class="panel-header">
          <span class="panel-title">Notifications</span>
          <div class="tabs">${tabsHtml}</div>
          <span class="version">v${VERSION}</span>
        </div>
        <div class="panel-content">
          ${this._renderTab()}
        </div>
      </div>`;

    this._attachTabListeners();
    this._attachNavListeners();
    if (this._activeTab === "settings") this._attachSettingsListeners();
    if (this._activeTab === "supervision") this._attachSupervisionListeners();
    if (this._activeTab === "modules") this._loadModulesTab();
  }

  _renderTab() {
    switch (this._activeTab) {
      case "users":
        return this._renderUsers(this._discoverUsers());
      case "modules":
        return this._wrapSection("Taxonomie modules", `<div class="empty" id="modules-loading">Chargement…</div>`);
      case "audit":
        return this._wrapSection(
          "Couverture personnes HA",
          this._renderAudit(this._auditPersons(this._discoverUsers()))
        );
      case "settings":
        return this._hasNotifEntities()
          ? this._renderSettings(this._discoverUsers())
          : this._renderSetupGuide();
      default:
        return this._wrapSection(
          "Supervision packages",
          this._renderSupervisionV2(this._discoverPackages(), true)
        );
    }
  }

  // ── Decouverte ───────────────────────────────────────────────────────────────

  _discoverUsers() {
    return Object.keys(this._hass.states || {})
      .filter((id) => id.startsWith("text.notif_") && id.endsWith("_label"))
      .map((id) => {
        const slug = id.slice("text.notif_".length, -"_label".length);
        return {
          slug,
          label: this._state(id),
          email: this._state(`text.notif_${slug}_email`),
          emailEnabled: this._boolState(`switch.notif_${slug}_email_enabled`),
          pushTarget: this._state(`text.notif_${slug}_push_target`),
          pushEnabled: this._boolState(`switch.notif_${slug}_push_enabled`),
          roles: ["role_admin", "role_proprietaire", "role_resident", "role_utilisateur"]
            .filter((k) => this._boolState(`switch.notif_${slug}_${k}`) === true)
            .map((k) => k.replace("role_", "")),
        };
      })
      .filter((u) => this._isUseful(u.label))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));
  }

  _discoverPackages() {
    const LEVEL_LABELS = {
      desactive: "Désactivé",
      utilisateur: "Utilisateur",
      resident: "Résident",
      proprietaire: "Propriétaire",
    };
    return Object.keys(this._hass.states || {})
      .filter((id) => id.startsWith("input_select.") && id.endsWith("_notification_level"))
      .map((id) => {
        const pkg = id.slice("input_select.".length, -"_notification_level".length);
        const adminEntity = `input_boolean.${pkg}_notif_admin`;
        const level = this._state(id) || "desactive";
        return {
          pkg,
          levelEntity: id,
          adminEntity,
          level,
          levelLabel: LEVEL_LABELS[level] || level,
          adminOn: this._boolState(adminEntity),
          adminExists: Boolean(this._hass.states[adminEntity]),
        };
      })
      .filter((p) => p.adminExists)
      .sort((a, b) => a.pkg.localeCompare(b.pkg));
  }

  _resolveSettingsAccess() {
    if (!this._hass) return "none";
    if (this._hass.user?.is_admin) return "write";
    const haName = (this._hass.user?.name || "").toLowerCase();
    if (!haName) return "none";
    const slug = Object.keys(this._hass.states || {})
      .filter((id) => id.startsWith("text.notif_") && id.endsWith("_label"))
      .map((id) => id.slice("text.notif_".length, -"_label".length))
      .find((s) => {
        const label = (this._state(`text.notif_${s}_label`) || "").toLowerCase();
        return label === haName || s === haName.replace(/[^a-z0-9]/g, "_");
      });
    if (!slug) return "none";
    if (this._boolState(`switch.notif_${slug}_role_admin`) === true) return "write";
    if (this._boolState(`switch.notif_${slug}_role_proprietaire`) === true) return "read";
    return "none";
  }

  _auditPersons(users) {
    const configured = new Set([
      ...users.map((u) => this._normalize(u.label)),
      ...users.map((u) => this._normalize(u.slug)),
    ]);
    const persons = Object.entries(this._hass.states || {})
      .filter(([id]) => id.startsWith("person."))
      .map(([id, s]) => ({ id, name: s.attributes?.friendly_name || id.slice(7) }))
      .sort((a, b) => a.name.localeCompare(b.name, "fr"));
    const missing = persons.filter((p) => {
      const keys = [
        this._normalize(p.name),
        this._normalize(p.id),
        this._normalize(p.id.slice(7)),
      ];
      return !keys.some((k) => configured.has(k));
    });
    return { persons, missing };
  }

  _hasNotifEntities() {
    return Object.keys(this._hass.states || {}).some(
      (id) => id.startsWith("text.notif_") || id.startsWith("switch.notif_")
    );
  }

  _detectMobileApps() {
    const notify = this._hass.services?.notify ?? {};
    return Object.keys(notify)
      .filter((k) => k.startsWith("mobile_app_"))
      .map((k) => `notify.${k}`)
      .sort();
  }

  _isSelf(slug) {
    if (!this._hass.user) return false;
    const haName = (this._hass.user.name || "").toLowerCase();
    const label = (this._state(`text.notif_${slug}_label`) || "").toLowerCase();
    return label === haName || slug === haName.replace(/[^a-z0-9]/g, "_");
  }

  _toSlug(name) {
    return String(name || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 30);
  }

  // ── Rendus ───────────────────────────────────────────────────────────────────

  _wrapSection(title, content) {
    return `<section><h3>${this._escape(title)}</h3>${content}</section>`;
  }

  _renderUsers(users) {
    if (!users.length)
      return `<div class="empty">Aucun utilisateur notification détecté.</div>`;
    const tiles = users
      .map((u) => {
        const ok = u.emailEnabled || u.pushEnabled || u.roles.length > 0;
        return `<article class="tile">
          <div class="tile-head">
            <strong>${this._escape(u.label)}</strong>
            ${this._badge(ok ? "OK" : "Incomplet", ok ? "ok" : "warn")}
          </div>
          <div class="rows">
            ${this._row("Email", u.emailEnabled === true ? "Actif" : "Inactif", u.email)}
            ${this._row("Push", u.pushEnabled === true ? "Actif" : "Inactif", u.pushTarget)}
            ${this._row("Niveaux", u.roles.length ? u.roles.join(", ") : "Aucun", "")}
          </div>
        </article>`;
      })
      .join("");
    return `<div class="grid">${tiles}</div>`;
  }

  _renderAudit(audit) {
    const ok = audit.missing.length === 0;
    const missingHtml = audit.missing.length
      ? audit.missing.map((p) => `<li>${this._escape(p.name)}</li>`).join("")
      : `<li>Aucune personne non couverte.</li>`;
    return `<article class="tile wide">
      <div class="tile-head">
        <strong>Couverture personnes HA</strong>
        ${this._badge(ok ? "OK" : "À vérifier", ok ? "ok" : "warn")}
      </div>
      <ul class="audit-list">${missingHtml}</ul>
    </article>`;
  }

  _renderSupervisionV2(packages, editable) {
    if (!packages.length)
      return `<div class="empty">Aucun package métier détecté (input_select.*_notification_level introuvable).</div>`;
    const LEVEL_OPTIONS = [
      ["desactive", "Désactivé"],
      ["utilisateur", "Utilisateur"],
      ["resident", "Résident"],
      ["proprietaire", "Propriétaire"],
    ];
    const tiles = packages
      .map((p) => {
        const levelCtrl = editable
          ? `<select class="pkg-level-select" data-entity="${this._escape(p.levelEntity)}">
              ${LEVEL_OPTIONS.map(
                ([val, lbl]) =>
                  `<option value="${val}" ${val === p.level ? "selected" : ""}>${lbl}</option>`
              ).join("")}
             </select>`
          : `<b>${this._escape(p.levelLabel)}</b>`;

        const adminCtrl = editable
          ? `<label class="toggle">
               <input type="checkbox" class="pkg-admin-toggle" data-entity="${this._escape(p.adminEntity)}" ${p.adminOn ? "checked" : ""}>
               <span class="slider"></span>
             </label>`
          : `<b>${p.adminOn === true ? "Actif" : "Inactif"}</b>`;

        const pkgLabel = p.pkg.replace(/_/g, " ");
        return `<article class="tile">
          <div class="tile-head"><strong>${this._escape(pkgLabel)}</strong></div>
          <div class="rows">
            <div class="row"><span>Niveau</span>${levelCtrl}</div>
            <div class="row toggle-row"><span>Admin</span>${adminCtrl}</div>
          </div>
        </article>`;
      })
      .join("");
    return `<div class="grid">${tiles}</div>`;
  }

  _renderSettings(users) {
    const access = this._resolveSettingsAccess();
    if (access === "none")
      return `<div class="banner read-banner">Accès non autorisé.</div>`;
    const editable = access === "write";
    const mobileApps = this._detectMobileApps();

    const banner = editable
      ? `<div class="banner edit-banner">Mode édition — modifications appliquées immédiatement</div>`
      : `<div class="banner read-banner">Lecture seule (rôle propriétaire).</div>`;

    const smtpHtml = this._settingsToggle(
      "switch.notifications_manager_smtp_active",
      "Canal email global (SMTP)",
      this._boolState("switch.notifications_manager_smtp_active"),
      editable
    );

    const rolesLabels = [
      ["Admin", "role_admin"],
      ["Propriétaire", "role_proprietaire"],
      ["Résident", "role_resident"],
      ["Utilisateur", "role_utilisateur"],
    ];

    const userTiles = users
      .map((u) => {
        if (editable && this._removeConfirm === u.slug)
          return this._renderRemoveConfirm(u);
        const removeBtn =
          editable && !this._isSelf(u.slug)
            ? `<button class="danger-btn" data-remove-user="${this._escape(u.slug)}">Retirer</button>`
            : "";
        return `<article class="tile">
          <div class="tile-head">
            <strong>${this._escape(u.label)}</strong>
            ${removeBtn}
          </div>
          <div class="rows">
            ${this._settingsToggle(`switch.notif_${u.slug}_email_enabled`, "Email", u.emailEnabled, editable)}
            ${
              editable
                ? `<div class="row"><input type="email" class="form-input" data-email-entity="text.notif_${this._escape(u.slug)}_email" placeholder="adresse@exemple.fr" value="${this._escape(u.email || "")}"></div>`
                : u.email
                ? `<div class="row"><span class="email-display">${this._escape(u.email)}</span></div>`
                : ""
            }
            ${this._settingsPushRow(u, mobileApps, editable)}
            ${rolesLabels
              .map(([name, key]) =>
                this._settingsToggle(
                  `switch.notif_${u.slug}_${key}`,
                  name,
                  this._boolState(`switch.notif_${u.slug}_${key}`),
                  editable
                )
              )
              .join("")}
          </div>
        </article>`;
      })
      .join("");

    let unconfiguredHtml = "";
    if (editable) {
      const audit = this._auditPersons(users);
      if (audit.missing.length === 0) {
        unconfiguredHtml = `<p class="empty">Toutes les personnes HA ont un profil notifications.</p>`;
      } else {
        unconfiguredHtml = audit.missing
          .map((p) => {
            if (this._addExpanded === p.id) return this._renderAddForm(p);
            return `<div class="person-row">
              <span>${this._escape(p.name)}</span>
              <button class="add-btn" data-add-person="${this._escape(p.id)}" data-person-name="${this._escape(p.name)}">+ Ajouter</button>
            </div>`;
          })
          .join("");
      }
    }

    return `
      ${banner}
      <section>
        <h3>Canal global</h3>
        <article class="tile wide"><div class="rows">${smtpHtml}</div></article>
      </section>
      ${
        users.length || editable
          ? `<section>
              <h3>Utilisateurs configurés</h3>
              ${users.length ? `<div class="grid">${userTiles}</div>` : `<p class="empty">Aucun utilisateur configuré.</p>`}
             </section>`
          : ""
      }
      ${
        editable
          ? `<section>
              <h3>Personnes sans profil</h3>
              <article class="tile wide"><div class="person-list">${unconfiguredHtml}</div></article>
             </section>`
          : ""
      }`;
  }

  _renderSetupGuide() {
    return `<div class="setup-guide">
      <div class="setup-icon">⚙️</div>
      <h3>Configuration requise</h3>
      <p>L'intégration <code>notifications_manager</code> n'est pas chargée ou aucun utilisateur n'est encore configuré.</p>
      <ol>
        <li>Installez <code>notifications_manager</code> via HACS ou dans <code>custom_components/</code></li>
        <li>Ajoutez <code>notifications_manager:</code> à <code>configuration.yaml</code></li>
        <li>Redémarrez Home Assistant</li>
      </ol>
    </div>`;
  }

  _renderAddForm(person) {
    const f = this._addForm;
    const slug = this._toSlug(person.name);
    const slugConflict = this._isUseful(this._state(`text.notif_${slug}_label`));
    const rolesLabels = [
      ["Admin", "admin"],
      ["Propriétaire", "proprietaire"],
      ["Résident", "resident"],
      ["Utilisateur", "utilisateur"],
    ];
    const rolesHtml = rolesLabels
      .map(
        ([name, key]) =>
          `<label class="role-check">
        <input type="checkbox" data-role="${key}" ${f.roles?.[key] ? "checked" : ""}> ${this._escape(name)}
      </label>`
      )
      .join("");
    const mobileApps = this._detectMobileApps();
    const pushOpts =
      mobileApps.length > 1
        ? `<select class="push-select add-push-select">
            <option value="">(saisie manuelle)</option>
            ${mobileApps.map((a) => `<option value="${this._escape(a)}" ${f.pushTarget === a ? "selected" : ""}>${this._escape(a)}</option>`).join("")}
           </select>`
        : `<input type="text" class="form-input" data-field="pushTarget" placeholder="notify.mobile_app_..." value="${this._escape(f.pushTarget || mobileApps[0] || "")}">`;

    return `<div class="form-card" data-form-person="${this._escape(person.id)}" data-form-slug="${this._escape(slug)}">
      <div class="form-title">${this._escape(person.name)} <span class="form-slug-hint">${this._escape(slug)}</span></div>
      ${slugConflict ? `<div class="banner slug-conflict-banner">Identifiant <code>${this._escape(slug)}</code> déjà utilisé.</div>` : ""}
      <div class="form-rows">
        <label>Email<input type="text" class="form-input" data-field="email" placeholder="adresse@exemple.fr" value="${this._escape(f.email || "")}" ${slugConflict ? "disabled" : ""}></label>
        <label>Push cible${pushOpts}</label>
        <div class="roles-row">${rolesHtml}</div>
      </div>
      <div class="form-actions">
        <button class="add-confirm-btn" data-confirm-add="${this._escape(person.id)}" ${slugConflict ? "disabled" : ""}>Confirmer</button>
        <button class="cancel-btn" data-cancel-add="${this._escape(person.id)}">Annuler</button>
      </div>
    </div>`;
  }

  _renderRemoveConfirm(user) {
    return `<article class="tile tile-danger">
      <div class="tile-head"><strong>${this._escape(user.label)}</strong></div>
      <p class="danger-msg">Supprimer ce profil ? Toutes les entités seront retirées.</p>
      <div class="form-actions">
        <button class="danger-confirm-btn" data-confirm-remove="${this._escape(user.slug)}">Confirmer</button>
        <button class="cancel-btn" data-cancel-remove="${this._escape(user.slug)}">Annuler</button>
      </div>
    </article>`;
  }

  // ── Composants settings ──────────────────────────────────────────────────────

  _settingsToggle(entityId, label, value, editable) {
    const allowed = SETTINGS_ALLOWLIST.test(entityId);
    if (editable && allowed) {
      return `<div class="row toggle-row">
        <span>${this._escape(label)}</span>
        <label class="toggle">
          <input type="checkbox" data-entity="${this._escape(entityId)}" ${value === true ? "checked" : ""}>
          <span class="slider"></span>
        </label>
      </div>`;
    }
    const display = value === true ? "Actif" : value === false ? "Inactif" : "—";
    return this._row(label, display, "");
  }

  _settingsPushRow(user, mobileApps, editable) {
    const toggleHtml = this._settingsToggle(
      `switch.notif_${user.slug}_push_enabled`,
      "Push",
      user.pushEnabled,
      editable
    );
    if (editable && mobileApps.length > 1) {
      const current = user.pushTarget || "";
      const opts = [
        `<option value="" ${!current ? "selected" : ""}>(saisie manuelle)</option>`,
        ...mobileApps.map(
          (app) =>
            `<option value="${this._escape(app)}" ${current === app ? "selected" : ""}>${this._escape(app)}</option>`
        ),
      ].join("");
      return (
        toggleHtml +
        `<div class="row"><span>Cible push</span>
        <select class="push-select" data-push-entity="${this._escape(`text.notif_${user.slug}_push_target`)}">${opts}</select></div>`
      );
    }
    return toggleHtml;
  }

  // ── Modules tab ─────────────────────────────────────────────────────────────

  async _loadModulesTab() {
    try {
      const data = await this._hass.callApi("GET", "notifications_manager/modules");
      const el = this.shadowRoot.querySelector("#modules-loading");
      if (el) el.outerHTML = this._renderModules(data);
    } catch (e) {
      const el = this.shadowRoot.querySelector("#modules-loading");
      if (el) el.textContent = "Erreur chargement taxonomie modules.";
    }
  }

  _renderModules(data) {
    const LEVEL_LABELS = {
      desactive: "Désactivé", utilisateur: "Utilisateur",
      resident: "Résident", proprietaire: "Propriétaire",
    };
    const renderGroup = (modules, typeBadge, typeLabel) => {
      if (!modules || !modules.length)
        return `<p class="empty">Aucun module ${typeLabel}.</p>`;
      const tiles = modules.map((mod) => {
        const levelEnt = `input_select.${mod}_notification_level`;
        const adminEnt = `input_boolean.${mod}_notif_admin`;
        const level = (this._hass.states[levelEnt]?.state) || "—";
        const adminOn = this._boolState(adminEnt);
        const levelLabel = LEVEL_LABELS[level] || level;
        const active = level !== "desactive" || adminOn === true;
        return `<article class="tile">
          <div class="tile-head">
            <strong>${this._escape(mod.replace(/_/g, " "))}</strong>
            ${this._badge(typeBadge, typeBadge === "Core" ? "ok" : "info")}
          </div>
          <div class="rows">
            <div class="row"><span>Niveau</span><b>${this._escape(levelLabel)}</b></div>
            <div class="row"><span>Admin</span><b>${adminOn === true ? "Actif" : "Inactif"}</b></div>
            <div class="row"><span>Statut</span>${this._badge(active ? "Actif" : "Silencieux", active ? "ok" : "warn")}</div>
          </div>
        </article>`;
      }).join("");
      return `<h4 style="margin:1rem 0 .5rem">${typeLabel}</h4><div class="grid">${tiles}</div>`;
    };
    return renderGroup(data.core, "Core", "Modules natifs (core)")
      + renderGroup(data.subscribers, "Souscripteur", "Modules souscripteurs");
  }

  // ── Listeners ────────────────────────────────────────────────────────────────

  _attachTabListeners() {
    this.shadowRoot.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this._activeTab = e.target.dataset.tab;
        this._addExpanded = null;
        this._removeConfirm = null;
        this._render();
      });
    });
  }

  _navigate(path) {
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _attachNavListeners() {
    this.shadowRoot.querySelectorAll(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => this._navigate(btn.dataset.nav));
    });
  }

  _attachSettingsListeners() {
    const root = this.shadowRoot;

    root.querySelectorAll("input[data-entity]").forEach((input) => {
      input.addEventListener("change", (e) => {
        const id = e.target.dataset.entity;
        if (SETTINGS_ALLOWLIST.test(id)) {
          const domain = id.startsWith("switch.") ? "switch" : "input_boolean";
          this._hass.callService(domain, "toggle", { entity_id: id });
        }
      });
    });

    root.querySelectorAll("input[data-email-entity]").forEach((input) => {
      input.addEventListener("change", (e) => {
        const id = e.target.dataset.emailEntity;
        if (EMAIL_ALLOWLIST.test(id)) {
          this._hass.callService("text", "set_value", {
            entity_id: id,
            value: e.target.value.trim(),
          });
        }
      });
    });

    root.querySelectorAll("select.push-select[data-push-entity]").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        const id = e.target.dataset.pushEntity;
        if (e.target.value && PUSH_TARGET_ALLOWLIST.test(id)) {
          this._hass.callService("text", "set_value", {
            entity_id: id,
            value: e.target.value,
          });
        }
      });
    });

    root.querySelectorAll("[data-remove-user]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this._removeConfirm = e.currentTarget.dataset.removeUser;
        this._addExpanded = null;
        this._render();
      });
    });

    root.querySelectorAll("[data-confirm-remove]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this._hass.callService("notifications_manager", "remove_user", {
          id: e.currentTarget.dataset.confirmRemove,
        });
        this._removeConfirm = null;
        this._render();
      });
    });

    root.querySelectorAll("[data-cancel-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._removeConfirm = null;
        this._render();
      });
    });

    root.querySelectorAll("[data-add-person]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const personName = e.currentTarget.dataset.personName || "";
        this._addExpanded = e.currentTarget.dataset.addPerson;
        this._addForm = {
          label: personName,
          email: "",
          pushTarget: this._detectMobileApps()[0] || "",
          roles: {},
        };
        this._removeConfirm = null;
        this._render();
      });
    });

    root.querySelectorAll(".form-card input[data-field]").forEach((input) => {
      input.addEventListener("input", (e) => {
        this._addForm[e.target.dataset.field] = e.target.value;
      });
    });

    root.querySelectorAll(".add-push-select").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        this._addForm.pushTarget = e.target.value;
      });
    });

    root.querySelectorAll(".form-card input[data-role]").forEach((cb) => {
      cb.addEventListener("change", (e) => {
        if (!this._addForm.roles) this._addForm.roles = {};
        this._addForm.roles[e.target.dataset.role] = e.target.checked;
      });
    });

    root.querySelectorAll("[data-confirm-add]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const f = this._addForm;
        const formCard = root.querySelector(".form-card");
        const id = (formCard?.dataset.formSlug || "").trim();
        const label = (f.label || "").trim();
        const emailInput = root.querySelector(".form-card input[data-field='email']");
        const pushInput = root.querySelector(".form-card input[data-field='pushTarget']");
        const email = (emailInput?.value || f.email || "").trim();
        const pushTarget =
          (pushInput?.value || f.pushTarget || "").trim() ||
          root.querySelector(".add-push-select")?.value ||
          "";

        if (!id || !/^[a-z0-9][a-z0-9_]{0,29}$/.test(id)) return;

        const roles = {};
        root.querySelectorAll(".form-card input[data-role]").forEach((cb) => {
          roles[cb.dataset.role] = cb.checked;
        });

        this._hass.callService("notifications_manager", "add_user", {
          id,
          label,
          email,
          email_enabled: Boolean(email),
          push_target: pushTarget,
          push_enabled: Boolean(pushTarget),
          roles,
        });
        this._addExpanded = null;
        this._addForm = {};
        this._render();
      });
    });

    root.querySelectorAll("[data-cancel-add]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._addExpanded = null;
        this._addForm = {};
        this._render();
      });
    });
  }

  _attachSupervisionListeners() {
    const root = this.shadowRoot;

    root.querySelectorAll("select.pkg-level-select").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        const id = e.target.dataset.entity;
        if (PKG_LEVEL_ALLOWLIST.test(id)) {
          this._hass.callService("input_select", "select_option", {
            entity_id: id,
            option: e.target.value,
          });
        }
      });
    });

    root.querySelectorAll("input.pkg-admin-toggle").forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const id = e.target.dataset.entity;
        if (PKG_ADMIN_ALLOWLIST.test(id)) {
          this._hass.callService("input_boolean", "toggle", { entity_id: id });
        }
      });
    });
  }

  // ── Utilitaires HTML ─────────────────────────────────────────────────────────

  _row(label, value, detail) {
    const det = this._isUseful(detail) ? `<small>${this._escape(detail)}</small>` : "";
    return `<div class="row"><span>${this._escape(label)}</span><b>${this._escape(value)}</b>${det}</div>`;
  }

  _badge(text, kind) {
    return `<span class="badge ${kind}">${this._escape(text)}</span>`;
  }

  _state(entityId) {
    const v = this._hass.states?.[entityId]?.state;
    return this._isUseful(v) ? String(v) : "";
  }

  _boolState(entityId) {
    const v = this._hass.states?.[entityId]?.state;
    if (v === "on") return true;
    if (v === "off") return false;
    return null;
  }

  _isUseful(v) {
    return (
      v !== undefined &&
      v !== null &&
      !["", "unknown", "unavailable", "none"].includes(String(v).trim().toLowerCase())
    );
  }

  _normalize(v) {
    return String(v || "").trim().toLowerCase();
  }

  _escape(v) {
    return String(v ?? "").replace(
      /[&<>'"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c])
    );
  }

  // ── Styles ───────────────────────────────────────────────────────────────────

  _styles() {
    return `
      :host{display:block;height:100%;background:var(--primary-background-color)}
      .panel{display:flex;flex-direction:column;height:100%;max-width:1200px;margin:0 auto;padding:0 16px;box-sizing:border-box}
      .panel-nav{display:flex;gap:4px;padding:8px 0 6px;border-bottom:1px solid var(--divider-color)}
      .nav-btn{display:inline-flex;align-items:center;gap:5px;background:transparent;border:none;cursor:pointer;padding:4px 10px;border-radius:20px;font-size:12px;color:var(--secondary-text-color);transition:.15s;font-family:inherit}
      .nav-btn ha-icon{--mdc-icon-size:16px;color:inherit}
      .nav-btn:hover{background:var(--secondary-background-color,rgba(0,0,0,.06));color:var(--primary-color)}
      .panel-header{display:flex;align-items:center;gap:16px;padding:10px 0;border-bottom:1px solid var(--divider-color);flex-wrap:wrap}
      .panel-title{font-size:18px;font-weight:700;color:var(--primary-text-color);white-space:nowrap}
      .version{color:var(--secondary-text-color);font-size:11px;white-space:nowrap;margin-left:auto}
      .tabs{display:flex;gap:4px;flex-wrap:wrap}
      .tab{background:transparent;border:1px solid var(--divider-color);border-radius:20px;padding:5px 14px;font-size:13px;cursor:pointer;color:var(--secondary-text-color);transition:.15s}
      .tab:hover{border-color:var(--primary-color);color:var(--primary-color)}
      .tab.active{background:var(--primary-color);border-color:var(--primary-color);color:#fff;font-weight:600}
      .panel-content{flex:1;overflow-y:auto;padding:16px 0}
      h3{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--secondary-text-color);margin:0 0 10px}
      section{margin-bottom:20px}
      .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
      .tile{border:1px solid var(--divider-color);border-radius:12px;padding:12px;background:var(--card-background-color)}
      .wide{grid-column:1/-1}
      .tile-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}
      .badge{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600;white-space:nowrap}
      .badge.ok{background:rgba(76,175,80,.15);color:var(--success-color,#43a047)}
      .badge.warn{background:rgba(255,152,0,.15);color:var(--warning-color,#fb8c00)}
      .badge.info{background:rgba(33,150,243,.15);color:var(--info-color,#1976d2)}
      .rows{display:grid;gap:6px}
      .row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;font-size:13px}
      .row span{color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .row b{font-weight:600;text-align:right;white-space:nowrap}
      .row small{grid-column:1/-1;color:var(--secondary-text-color);font-size:11px;overflow:hidden;text-overflow:ellipsis}
      .audit-list{margin:4px 0 0;padding-left:18px;font-size:13px;line-height:1.8}
      .empty{color:var(--secondary-text-color);padding:8px 0;font-size:13px}
      .banner{border-radius:8px;padding:8px 12px;font-size:12px;margin-bottom:14px}
      .edit-banner{background:rgba(33,150,243,.1);color:var(--info-color,#1e88e5)}
      .read-banner{background:rgba(0,0,0,.04);color:var(--secondary-text-color)}
      .toggle-row{align-items:center}
      .toggle{position:relative;display:inline-flex;width:38px;height:22px;flex-shrink:0;cursor:pointer}
      .toggle input{opacity:0;width:0;height:0;position:absolute}
      .slider{position:absolute;inset:0;background:var(--divider-color,#ccc);border-radius:22px;transition:.2s}
      .slider::before{content:"";position:absolute;left:3px;top:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
      input:checked+.slider{background:var(--primary-color,#03a9f4)}
      input:checked+.slider::before{transform:translateX(16px)}
      select.push-select,select.pkg-level-select{border:1px solid var(--divider-color);border-radius:6px;padding:3px 6px;font-size:12px;background:var(--card-background-color);color:var(--primary-text-color);max-width:160px}
      .add-btn{background:var(--primary-color,#03a9f4);color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
      .danger-btn{background:transparent;color:var(--error-color,#e53935);border:1px solid var(--error-color,#e53935);border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer}
      .danger-confirm-btn{background:var(--error-color,#e53935);color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
      .cancel-btn{background:transparent;color:var(--secondary-text-color);border:1px solid var(--divider-color);border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
      .add-confirm-btn{background:var(--primary-color,#03a9f4);color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
      .add-confirm-btn:disabled{opacity:.4;cursor:default}
      .person-list{display:grid;gap:8px}
      .person-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 0;font-size:13px}
      .tile-danger{border-color:var(--error-color,#e53935)}
      .danger-msg{font-size:12px;color:var(--secondary-text-color);margin:6px 0 10px}
      .form-card{border:1px solid var(--primary-color,#03a9f4);border-radius:12px;padding:12px;background:var(--card-background-color)}
      .form-title{font-weight:700;font-size:13px;margin-bottom:10px;display:flex;align-items:baseline;gap:8px}
      .form-slug-hint{font-size:11px;font-weight:400;color:var(--secondary-text-color);font-family:monospace}
      .form-rows{display:grid;gap:8px;margin-bottom:12px}
      .form-rows label{font-size:12px;color:var(--secondary-text-color);display:grid;gap:3px}
      .form-input{border:1px solid var(--divider-color);border-radius:6px;padding:4px 8px;font-size:12px;background:var(--card-background-color);color:var(--primary-text-color);width:100%;box-sizing:border-box}
      .email-display{font-size:11px;color:var(--secondary-text-color)}
      .slug-conflict-banner{background:rgba(229,57,53,.08);color:var(--error-color,#e53935);border-radius:6px;padding:6px 10px;font-size:12px;margin-bottom:10px}
      .roles-row{display:flex;gap:10px;flex-wrap:wrap}
      .role-check{display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;color:var(--primary-text-color)}
      .form-actions{display:flex;gap:8px;flex-wrap:wrap}
      .setup-guide{padding:24px;text-align:center}
      .setup-icon{font-size:40px;margin-bottom:12px}
      .setup-guide h3{font-size:15px;font-weight:700;margin:0 0 10px}
      .setup-guide p,.setup-guide li{font-size:13px;color:var(--secondary-text-color);line-height:1.7}
      .setup-guide ol{text-align:left;display:inline-block;padding-left:20px}
      .setup-guide code{background:rgba(0,0,0,.08);padding:1px 5px;border-radius:4px;font-size:11px}
      @media(max-width:600px){
        .panel{padding:0 10px}
        .panel-title{font-size:15px}
        .grid{grid-template-columns:1fr}
        .tabs{gap:3px}
        .tab{padding:4px 10px;font-size:12px}
      }
    `;
  }
}

if (!customElements.get("notifications-supervision-panel")) {
  customElements.define("notifications-supervision-panel", NotificationsSupervisionPanel);
}

console.info(
  `%cnotifications-supervision-panel v${VERSION} loaded`,
  "color:#03a9f4;font-weight:bold;background:#e3f2fd;padding:2px 6px;border-radius:4px"
);
