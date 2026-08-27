/* global customElements, HTMLElement, window */

const VACUUM_QUEUE_DOMAIN = "vacuum_queue";

const DEFAULT_LABELS = {
  rooms: "Rooms",
  actions: "Actions",
  start: "Start vacuum",
  skip: "Skip room",
  return_home: "Return home",
  no_current_room: "No current room",
  no_device: "No Vacuum Queue device found",
  multiple_devices: "Set device_id because multiple queues exist",
  loading: "Loading Vacuum Queue…",
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

class VacuumQueueCard extends HTMLElement {
  setConfig(config) {
    if (!config || config.type !== "custom:vacuum-queue-card") {
      throw new Error("Vacuum Queue card requires a valid configuration");
    }
    this._config = config;
    this._deviceId = null;
    this._entities = [];
    this._discoveryKey = null;
    this._discoveryDone = false;
    this._error = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._discoverEntities();
    this._render();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {
      show_return_home: false,
    };
  }

  async _callWebSocket(message) {
    if (this._hass.callWS) {
      return this._hass.callWS(message);
    }
    return this._hass.connection.sendMessagePromise(message);
  }

  async _discoverEntities() {
    if (!this._hass || !this._config) return;

    const requestedDevice = this._config.device_id || "auto";
    if (this._discoveryKey === requestedDevice && this._discoveryDone) return;
    this._discoveryKey = requestedDevice;
    this._discoveryDone = false;

    try {
      let queues;
      try {
        queues = await this._callWebSocket({ type: "vacuum_queue/list" });
      } catch (error) {
        queues = undefined;
      }
      if (Array.isArray(queues)) {
        this._applyQueues(queues);
        return;
      }

      const [devicesResponse, entitiesResponse] = await Promise.all([
        this._callWebSocket({ type: "config/device_registry/list" }),
        this._callWebSocket({ type: "config/entity_registry/list" }),
      ]);
      const devices = Array.isArray(devicesResponse)
        ? devicesResponse
        : devicesResponse.devices || [];
      const entities = Array.isArray(entitiesResponse)
        ? entitiesResponse
        : entitiesResponse.entities || [];
      const queueDevices = devices.filter((device) =>
        (device.identifiers || []).some(
          (identifier) =>
            Array.isArray(identifier) && identifier[0] === VACUUM_QUEUE_DOMAIN,
        ),
      );

      let device;
      if (this._config.device_id) {
        device = devices.find((candidate) => candidate.id === this._config.device_id);
      } else if (queueDevices.length === 1) {
        device = queueDevices[0];
      } else if (queueDevices.length > 1) {
        this._setError(DEFAULT_LABELS.multiple_devices);
        return;
      }

      if (!device) {
        this._setError(DEFAULT_LABELS.no_device);
        return;
      }

      this._deviceId = device.id;
      this._entities = entities
        .filter(
          (entry) =>
            entry.device_id === this._deviceId &&
            (entry.domain === "switch" || entry.domain === "button"),
        )
        .sort((left, right) => left.entity_id.localeCompare(right.entity_id));
      this._finishDiscovery();
    } catch (error) {
      this._setError(error.message || "Unable to discover Vacuum Queue entities");
    }
  }

  _applyQueues(queues) {
    const target = this._config.device_id
      ? queues.find((queue) => queue.device_id === this._config.device_id)
      : queues.length === 1
        ? queues[0]
        : null;

    if (queues.length > 1 && !this._config.device_id) {
      this._setError(DEFAULT_LABELS.multiple_devices);
      return;
    }
    if (!target) {
      this._setError(DEFAULT_LABELS.no_device);
      return;
    }

    this._deviceId = target.device_id;
    this._entities = [
      ...(target.switches || []).map((entry) => ({
        entity_id: entry.entity_id,
        domain: "switch",
        unique_id: entry.unique_id,
      })),
      ...(target.buttons || []).map((entry) => ({
        entity_id: entry.entity_id,
        domain: "button",
        unique_id: entry.unique_id,
      })),
    ].sort((left, right) => left.entity_id.localeCompare(right.entity_id));
    this._finishDiscovery();
  }

  _finishDiscovery() {
    this._discoveryDone = true;
    if (!this._entities.length) {
      this._error = `No Vacuum Queue switch or button entities found (device ${this._deviceId || "unknown"})`;
    } else {
      this._error = null;
    }
    this._render();
  }

  _setError(message) {
    this._error = message;
    this._entities = [];
    this._deviceId = null;
    this._discoveryDone = true;
    this._render();
  }

  _labels() {
    return { ...DEFAULT_LABELS, ...(this._config.labels || {}) };
  }

  _state(entry) {
    return entry ? this._hass?.states?.[entry.entity_id] : undefined;
  }

  _button(action) {
    return this._entities.find(
      (entry) =>
        entry.domain === "button" && entry.unique_id?.endsWith(`_${action}`),
    );
  }

  async _toggleRoom(entityId, turnOn) {
    await this._hass.callService("switch", turnOn ? "turn_on" : "turn_off", {
      entity_id: entityId,
    });
  }

  async _press(action) {
    const button = this._button(action);
    if (!button) return;
    await this._hass.callService("button", "press", {
      entity_id: button.entity_id,
    });
  }

  _icon(iconName, className = "icon") {
    const icon = element("ha-icon", className);
    icon.setAttribute("icon", iconName || "mdi:home-floor-1");
    return icon;
  }

  _renderRoom(entry) {
    const state = this._state(entry);
    const isOn = state?.state === "on";
    const room = element("button", `room${isOn ? " on" : ""}`);
    room.type = "button";
    room.append(this._icon(state?.attributes?.icon));
    room.append(element("span", "room-name", state?.attributes?.friendly_name || entry.entity_id));
    room.addEventListener("click", () => this._toggleRoom(entry.entity_id, !isOn));
    return room;
  }

  _renderAction(action, icon, label, currentRoom) {
    const button = this._button(action);
    if (!button) return null;
    const row = element("button", "action");
    row.type = "button";
    row.append(this._icon(icon));
    const text = element("span", "action-text");
    text.append(element("span", "action-label", label));
    if (action === "skip") {
      text.append(
        element(
          "span",
          "action-subtitle",
          currentRoom || this._labels().no_current_room,
        ),
      );
    }
    row.append(text);
    row.addEventListener("click", () => this._press(action));
    return row;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const labels = this._labels();
    const root = element("div", "card");
    const style = element("style");
    style.textContent = `
      :host { display: block; }
      .card { color: var(--primary-text-color); }
      h2 { font-size: 24px; font-weight: 400; margin: 4px 0 14px; }
      .section + .section { margin-top: 24px; }
      .rooms { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      button { font: inherit; color: inherit; cursor: pointer; border: 0; }
      .room { min-height: 68px; border-radius: 999px; background: var(--ha-card-background, var(--card-background-color)); display: flex; align-items: center; gap: 12px; padding: 8px 18px 8px 10px; text-align: left; transition: background .15s; }
      .room.on { background: var(--primary-color); color: var(--text-primary-color, white); }
      .icon { --mdc-icon-size: 28px; width: 48px; height: 48px; display: grid; place-items: center; border-radius: 50%; background: color-mix(in srgb, var(--primary-text-color) 9%, transparent); flex: 0 0 48px; }
      .room.on .icon { background: color-mix(in srgb, black 75%, transparent); }
      .room-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .actions { display: grid; gap: 12px; }
      .action { width: 100%; min-height: 68px; border-radius: 999px; background: var(--ha-card-background, var(--card-background-color)); display: flex; align-items: center; gap: 12px; padding: 8px 22px 8px 10px; text-align: left; }
      .action-text { display: grid; gap: 2px; }
      .action-label { font-weight: 600; }
      .action-subtitle { color: var(--secondary-text-color); font-size: .9em; }
      .message { color: var(--secondary-text-color); padding: 8px 0; }
      @media (max-width: 420px) { .rooms { grid-template-columns: 1fr; } }
    `;

    if (this._error) {
      root.append(element("div", "message", this._error));
      this.shadowRoot.replaceChildren(style, root);
      return;
    }
    if (!this._entities.length) {
      root.append(element("div", "message", labels.loading));
      this.shadowRoot.replaceChildren(style, root);
      return;
    }

    const roomEntries = this._entities
      .filter((entry) => entry.domain === "switch")
      .sort((left, right) => {
        const leftOrder = this._state(left)?.attributes?.queue_order ?? Number.MAX_SAFE_INTEGER;
        const rightOrder = this._state(right)?.attributes?.queue_order ?? Number.MAX_SAFE_INTEGER;
        return leftOrder - rightOrder || left.entity_id.localeCompare(right.entity_id);
      });
    const roomsSection = element("section", "section");
    roomsSection.append(element("h2", "", labels.rooms));
    const rooms = element("div", "rooms");
    roomEntries.forEach((entry) => rooms.append(this._renderRoom(entry)));
    roomsSection.append(rooms);
    root.append(roomsSection);

    const skipState = this._state(this._button("skip"));
    const currentRoom = skipState?.attributes?.current_room;
    const actionsSection = element("section", "section");
    actionsSection.append(element("h2", "", labels.actions));
    const actions = element("div", "actions");
    const start = this._renderAction("start", "mdi:play-circle-outline", labels.start);
    const skip = this._renderAction("skip", "mdi:skip-next", labels.skip, currentRoom);
    if (start) actions.append(start);
    if (skip) actions.append(skip);
    if (this._config.show_return_home) {
      const returnHome = this._renderAction(
        "return_home",
        "mdi:home-import-outline",
        labels.return_home,
      );
      if (returnHome) actions.append(returnHome);
    }
    actionsSection.append(actions);
    root.append(actionsSection);
    this.shadowRoot.replaceChildren(style, root);
  }
}

if (!customElements.get("vacuum-queue-card")) {
  customElements.define("vacuum-queue-card", VacuumQueueCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vacuum-queue-card",
  name: "Vacuum Queue",
  description: "Room switches and queue actions for Vacuum Queue.",
  preview: true,
});
