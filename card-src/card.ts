/**
 * syno-download-card — compact dashboard card for the Synology Download
 * Station integration. Compiled to
 * custom_components/synology_download_station/frontend/card.js and
 * auto-registered as a Lovelace resource by the integration.
 */

interface DownloadTask {
  id: string;
  title: string;
  status: string;
  size: number;
  downloaded: number;
  progress: number | null;
  speed_download: number;
  eta: number | null;
  completed_time: number;
}

interface LatestCompleted {
  title: string;
  size: number;
  completed_time: number;
}

interface HassEntity {
  state: string;
  attributes: {
    tasks?: DownloadTask[];
    latest_completed?: LatestCompleted | null;
    completed?: LatestCompleted[];
    [key: string]: unknown;
  };
}

interface HomeAssistant {
  states: Record<string, HassEntity | undefined>;
  callService(
    domain: string,
    service: string,
    data: Record<string, unknown>
  ): Promise<unknown>;
}

interface CardConfig {
  entity: string;
  title: string;
  show_add: boolean;
  show_completed: boolean;
  completed_count: number;
}

const CARD_TAG = "syno-download-card";
const SERVICE_DOMAIN = "synology_download_station";
const DEFAULT_ENTITY = "sensor.synology_download_station_active_downloads";

const CARD_CSS = `
ha-card { padding: 10px 12px 12px; font-size: 13px; line-height: 1.35; }
.hdr { display: flex; justify-content: space-between; align-items: baseline; font-weight: 500; margin-bottom: 4px; }
.spd { color: var(--secondary-text-color); font-size: 12px; font-weight: 400; }
.empty { color: var(--secondary-text-color); font-size: 12px; padding: 2px 0; }
.task { margin: 6px 0; }
.trow { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: var(--secondary-text-color); font-size: 11px; white-space: nowrap; }
.bar { height: 4px; border-radius: 2px; background: var(--divider-color); margin-top: 3px; overflow: hidden; }
.fill { height: 100%; background: var(--primary-color); transition: width 0.4s ease; }
.paused .fill { background: var(--warning-color, #b58e31); }
.done { margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--divider-color); font-size: 12px; color: var(--secondary-text-color); }
.drow { display: flex; justify-content: space-between; gap: 8px; margin: 2px 0; }
.ltitle { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.addrow { display: flex; gap: 6px; margin-top: 8px; }
input[type="text"] { flex: 1; min-width: 0; border: 1px solid var(--divider-color); border-radius: 6px; background: transparent; color: var(--primary-text-color); padding: 5px 8px; font-size: 12px; outline: none; }
input[type="text"]:focus { border-color: var(--primary-color); }
button { border: none; border-radius: 6px; background: var(--primary-color); color: var(--text-primary-color, #fff); cursor: pointer; padding: 4px 10px; font-size: 13px; }
button.ghost { background: transparent; border: 1px solid var(--divider-color); color: var(--primary-text-color); }
.status { margin-top: 6px; font-size: 11px; color: var(--secondary-text-color); }
.status.err { color: var(--error-color); }
`;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond >= 1e6) return `${(bytesPerSecond / 1e6).toFixed(1)} MB/s`;
  if (bytesPerSecond >= 1e3) return `${(bytesPerSecond / 1e3).toFixed(0)} kB/s`;
  return `${bytesPerSecond} B/s`;
}

function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

function formatAgo(epochSeconds: number): string {
  const delta = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (delta < 60) return "just now";
  if (delta < 3600) return `${Math.floor(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} h ago`;
  return `${Math.floor(delta / 86400)} d ago`;
}

class SynoDownloadCard extends HTMLElement {
  private config!: CardConfig;

  private hassObj?: HomeAssistant;

  private lastEntity?: HassEntity;

  private tasksEl!: HTMLElement;

  private completedEl!: HTMLElement;

  private speedEl!: HTMLElement;

  private statusEl!: HTMLElement;

  private inputEl!: HTMLInputElement;

  private fileEl!: HTMLInputElement;

  private statusTimer?: number;

  setConfig(config: Partial<CardConfig>): void {
    this.config = {
      entity: config.entity ?? DEFAULT_ENTITY,
      title: config.title ?? "Downloads",
      show_add: config.show_add ?? true,
      show_completed: config.show_completed ?? true,
      completed_count: config.completed_count ?? 3,
    };
    this.lastEntity = undefined;
    this.buildShell();
  }

  set hass(hass: HomeAssistant) {
    this.hassObj = hass;
    if (!this.config) return;
    const entity = hass.states[this.config.entity];
    if (entity === this.lastEntity) return;
    this.lastEntity = entity;
    this.renderDynamic(entity);
  }

  getCardSize(): number {
    return 3;
  }

  static getStubConfig(): Record<string, unknown> {
    return {};
  }

  private buildShell(): void {
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${CARD_CSS}</style>
      <ha-card>
        <div class="hdr">
          <span>${escapeHtml(this.config.title)}</span>
          <span class="spd"></span>
        </div>
        <div class="tasks"></div>
        <div class="done" hidden></div>
        <div class="addrow" ${this.config.show_add ? "" : "hidden"}>
          <input type="text" placeholder="magnet: or torrent URL" spellcheck="false" />
          <button class="send" title="Add link">&#10148;</button>
          <button class="pick ghost" title="Upload .torrent file">&#128194;</button>
          <input type="file" accept=".torrent,application/x-bittorrent" hidden />
        </div>
        <div class="status" hidden></div>
      </ha-card>`;
    this.tasksEl = root.querySelector(".tasks") as HTMLElement;
    this.completedEl = root.querySelector(".done") as HTMLElement;
    this.speedEl = root.querySelector(".spd") as HTMLElement;
    this.statusEl = root.querySelector(".status") as HTMLElement;
    this.inputEl = root.querySelector("input[type=text]") as HTMLInputElement;
    this.fileEl = root.querySelector("input[type=file]") as HTMLInputElement;
    (root.querySelector(".send") as HTMLElement).addEventListener("click", () =>
      this.submitUrl()
    );
    (root.querySelector(".pick") as HTMLElement).addEventListener("click", () =>
      this.fileEl.click()
    );
    this.inputEl.addEventListener("keydown", (ev: KeyboardEvent) => {
      if (ev.key === "Enter") this.submitUrl();
    });
    this.fileEl.addEventListener("change", () => this.uploadFile());
  }

  private renderDynamic(entity: HassEntity | undefined): void {
    if (!this.tasksEl) return;
    if (!entity) {
      this.tasksEl.innerHTML = `<div class="empty">Entity ${escapeHtml(
        this.config.entity
      )} not found</div>`;
      this.speedEl.textContent = "";
      this.completedEl.hidden = true;
      return;
    }
    const tasks = entity.attributes.tasks ?? [];
    const totalSpeed = tasks.reduce(
      (sum, task) => sum + (task.speed_download || 0),
      0
    );
    this.speedEl.textContent = totalSpeed > 0 ? `↓ ${formatSpeed(totalSpeed)}` : "";
    if (tasks.length === 0) {
      this.tasksEl.innerHTML = `<div class="empty">No active downloads</div>`;
    } else {
      this.tasksEl.innerHTML = tasks
        .map((task) => this.taskHtml(task))
        .join("");
    }
    const attrs = entity.attributes;
    const completed = (
      attrs.completed ?? (attrs.latest_completed ? [attrs.latest_completed] : [])
    ).slice(0, this.config.completed_count);
    if (this.config.show_completed && completed.length > 0) {
      this.completedEl.hidden = false;
      this.completedEl.innerHTML = completed
        .map(
          (item) => `
        <div class="drow">
          <span class="ltitle" title="${escapeHtml(item.title)}">&#10003; ${escapeHtml(
            item.title
          )}</span>
          <span class="meta">${
            item.completed_time ? formatAgo(item.completed_time) : ""
          }</span>
        </div>`
        )
        .join("");
    } else {
      this.completedEl.hidden = true;
    }
  }

  private taskHtml(task: DownloadTask): string {
    const progress = task.progress ?? 0;
    const paused = task.status === "paused";
    const meta: string[] = [`${progress.toFixed(0)}%`];
    if (paused) {
      meta.push("paused");
    } else {
      if (task.speed_download > 0) meta.push(formatSpeed(task.speed_download));
      if (task.eta) meta.push(`~${formatEta(task.eta)}`);
    }
    return `
      <div class="task${paused ? " paused" : ""}">
        <div class="trow">
          <span class="title" title="${escapeHtml(task.title)}">${escapeHtml(
            task.title
          )}</span>
          <span class="meta">${meta.join(" · ")}</span>
        </div>
        <div class="bar"><div class="fill" style="width:${Math.min(
          progress,
          100
        )}%"></div></div>
      </div>`;
  }

  private submitUrl(): void {
    const url = this.inputEl.value.trim();
    if (!url) return;
    void this.call("add_task", { url }).then((ok) => {
      if (ok) this.inputEl.value = "";
    });
  }

  private uploadFile(): void {
    const file = this.fileEl.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = String(reader.result).split(",", 2)[1] ?? "";
      void this.call("add_torrent", { torrent: base64, filename: file.name });
      this.fileEl.value = "";
    };
    reader.readAsDataURL(file);
  }

  private async call(
    service: string,
    data: Record<string, unknown>
  ): Promise<boolean> {
    if (!this.hassObj) return false;
    try {
      await this.hassObj.callService(SERVICE_DOMAIN, service, data);
      this.setStatus("Added ✓", false);
      return true;
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : ((err as { message?: string })?.message ?? String(err));
      this.setStatus(message, true);
      return false;
    }
  }

  private setStatus(message: string, isError: boolean): void {
    this.statusEl.hidden = false;
    this.statusEl.textContent = message;
    this.statusEl.classList.toggle("err", isError);
    if (this.statusTimer) window.clearTimeout(this.statusTimer);
    this.statusTimer = window.setTimeout(() => {
      this.statusEl.hidden = true;
    }, 5000);
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, SynoDownloadCard);
}

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

const globalWindow = window as unknown as { customCards?: CustomCardEntry[] };
globalWindow.customCards = globalWindow.customCards ?? [];
globalWindow.customCards.push({
  type: CARD_TAG,
  name: "Synology Download Card",
  description:
    "Compact Download Station progress with magnet/torrent submit box.",
  preview: false,
  documentationURL: "https://github.com/HugoGresse/syno-download-ha",
});
