export const SHARE_TOKEN_LENGTH = 22;

const ALPHABET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
const TOKEN_PATTERN = /^[A-Za-z0-9_-]+$/;

function getCrypto(): Crypto {
  if (typeof globalThis.crypto?.getRandomValues === "function") {
    return globalThis.crypto;
  }
  throw new Error("Secure random source (crypto.getRandomValues) unavailable");
}

export function generateShareToken(length: number = SHARE_TOKEN_LENGTH): string {
  const crypto = getCrypto();
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  let out = "";
  for (let i = 0; i < length; i++) {
    out += ALPHABET[bytes[i] & 63];
  }
  return out;
}

export function isValidShareToken(token: unknown): token is string {
  return (
    typeof token === "string" &&
    token.length === SHARE_TOKEN_LENGTH &&
    TOKEN_PATTERN.test(token)
  );
}
