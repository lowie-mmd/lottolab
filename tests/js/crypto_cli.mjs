// crypto.js 的 CLI 封裝，供跨語言互通測試（Python add_bet.py ↔ 瀏覽器 crypto.js）。
// 用法：
//   echo '<json>'     | node crypto_cli.mjs encrypt <passphrase>  → 印 envelope JSON
//   echo '<envelope>' | node crypto_cli.mjs decrypt <passphrase>  → 印明文 JSON
import { encryptJSON, decryptJSON } from "../../docs/crypto.js";

const [, , cmd, passphrase] = process.argv;
const input = await new Promise((res) => {
  let s = "";
  process.stdin.on("data", (c) => (s += c));
  process.stdin.on("end", () => res(s));
});

if (cmd === "encrypt") {
  const env = await encryptJSON(JSON.parse(input), passphrase);
  process.stdout.write(JSON.stringify(env));
} else if (cmd === "decrypt") {
  const obj = await decryptJSON(JSON.parse(input), passphrase);
  process.stdout.write(JSON.stringify(obj));
} else {
  process.stderr.write("usage: crypto_cli.mjs encrypt|decrypt <passphrase>\n");
  process.exit(2);
}
