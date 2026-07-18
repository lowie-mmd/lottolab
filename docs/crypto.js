// crypto.js — WebCrypto 封裝（規格 §7.2）。
// AES-256-GCM，金鑰由通關密語經 PBKDF2-SHA256（≥600k iterations、隨機 salt）導出。
// 密文以 JSON envelope 存放（salt/iv/ct 皆 base64），add_bet.py 使用相同格式 → 互通。
// 設計鐵律：明文只存在於瀏覽器記憶體與洛伊本機，永不進 repo（§7.2）。

export const KDF_ITERATIONS = 600000;
const SALT_BYTES = 16;
const IV_BYTES = 12;

const subtle = (globalThis.crypto || {}).subtle;

function u8ToB64(u8) {
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s);
}
function b64ToU8(b64) {
  const s = atob(b64);
  const u8 = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u8[i] = s.charCodeAt(i);
  return u8;
}

async function deriveKey(passphrase, salt, iterations) {
  const enc = new TextEncoder();
  const baseKey = await subtle.importKey(
    "raw", enc.encode(passphrase), { name: "PBKDF2" }, false, ["deriveKey"]
  );
  return subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

// 明文物件 → envelope。ct 含附加的 16-byte GCM tag（WebCrypto 預設）。
export async function encryptJSON(obj, passphrase, iterations = KDF_ITERATIONS) {
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const key = await deriveKey(passphrase, salt, iterations);
  const plaintext = new TextEncoder().encode(JSON.stringify(obj));
  const ct = new Uint8Array(await subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext));
  return {
    v: 1,
    kdf: "PBKDF2-SHA256",
    iter: iterations,
    salt: u8ToB64(salt),
    iv: u8ToB64(iv),
    ct: u8ToB64(ct),
  };
}

// envelope → 明文物件。密語錯誤時 GCM 驗證失敗 → 丟例外（呼叫端只顯示「無法解密」，不洩結構）。
export async function decryptJSON(envelope, passphrase) {
  const salt = b64ToU8(envelope.salt);
  const iv = b64ToU8(envelope.iv);
  const ct = b64ToU8(envelope.ct);
  const key = await deriveKey(passphrase, salt, envelope.iter || KDF_ITERATIONS);
  const plaintext = await subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
  return JSON.parse(new TextDecoder().decode(plaintext));
}
