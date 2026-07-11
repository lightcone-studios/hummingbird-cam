import Foundation
import CryptoKit

// sesign — Secure Enclave signing tool for the hummingbird-cam science harness.
//
// Subcommands:
//   sesign init [--pubkey-out PATH]   create/load the SE key; print public key PEM to stdout
//   sesign sign  --in PATH            sign the bytes of PATH; print base64 DER signature
//   sesign pubkey                     print the public key PEM
//   sesign fingerprint                print the key fingerprint (sha256 of raw pubkey, first 16 hex)
//
// The private key lives in the Secure Enclave and never leaves it. We persist only a
// wrapped, device-bound blob at ~/.config/hummingbird-science/se-key.blob (mode 0600) —
// that blob is useless on any machine but this one's enclave. Signatures are standard
// ECDSA P-256 over SHA-256 and verify with `openssl dgst -sha256 -verify` on any platform.

let fm = FileManager.default

func die(_ msg: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write(("sesign: " + msg + "\n").data(using: .utf8)!)
    exit(code)
}

func blobURL() -> URL {
    let base = fm.homeDirectoryForCurrentUser
        .appendingPathComponent(".config", isDirectory: true)
        .appendingPathComponent("hummingbird-science", isDirectory: true)
    try? fm.createDirectory(at: base, withIntermediateDirectories: true,
                            attributes: [.posixPermissions: 0o700])
    return base.appendingPathComponent("se-key.blob")
}

func loadOrCreateKey(create: Bool) -> SecureEnclave.P256.Signing.PrivateKey {
    let url = blobURL()
    if fm.fileExists(atPath: url.path) {
        guard let blob = try? Data(contentsOf: url) else { die("cannot read key blob at \(url.path)") }
        guard let key = try? SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: blob) else {
            die("key blob present but failed to load (wrong device, or corrupted)")
        }
        return key
    }
    if !create { die("no key found — run `sesign init` first", 3) }
    guard SecureEnclave.isAvailable else { die("Secure Enclave not available on this machine", 2) }
    guard let key = try? SecureEnclave.P256.Signing.PrivateKey() else { die("SE key generation failed") }
    do {
        try key.dataRepresentation.write(to: url, options: [.atomic])
        try fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
    } catch { die("failed to persist key blob: \(error)") }
    return key
}

func fingerprint(_ key: SecureEnclave.P256.Signing.PrivateKey) -> String {
    let digest = SHA256.hash(data: key.publicKey.rawRepresentation)
    return String(digest.map { String(format: "%02x", $0) }.joined().prefix(16))
}

var args = Array(CommandLine.arguments.dropFirst())
guard let cmd = args.first else { die("usage: sesign <init|sign|pubkey|fingerprint>", 64) }
args = Array(args.dropFirst())

func optValue(_ name: String) -> String? {
    if let i = args.firstIndex(of: name), i + 1 < args.count { return args[i + 1] }
    return nil
}

switch cmd {
case "init":
    let key = loadOrCreateKey(create: true)
    let pem = key.publicKey.pemRepresentation
    if let out = optValue("--pubkey-out") {
        try? pem.data(using: .utf8)!.write(to: URL(fileURLWithPath: out))
    }
    FileHandle.standardError.write("fingerprint \(fingerprint(key))\n".data(using: .utf8)!)
    print(pem, terminator: "")

case "pubkey":
    print(loadOrCreateKey(create: false).publicKey.pemRepresentation, terminator: "")

case "fingerprint":
    print(fingerprint(loadOrCreateKey(create: false)))

case "sign":
    let key = loadOrCreateKey(create: false)
    guard let path = optValue("--in") else { die("sign requires --in PATH", 64) }
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { die("cannot read --in \(path)") }
    guard let sig = try? key.signature(for: data) else { die("signing failed") }
    print(sig.derRepresentation.base64EncodedString())

default:
    die("unknown command \(cmd)", 64)
}
