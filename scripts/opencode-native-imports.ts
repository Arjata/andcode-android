/** Build-only experiment: make native file imports explicit, never bunfs assets. */
import type { BunPlugin } from "bun"
import { createHash } from "node:crypto"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import path from "node:path"

export function nativeImports(stage: string): BunPlugin {
  if (!path.isAbsolute(stage)) throw new Error("Native stage must be absolute")
  const seen = new Map<string, string>()
  const rows = new Set<string>()
  mkdirSync(path.join(stage, "native"), { recursive: true })
  return {
    name: "andcode-preinstalled-native-imports",
    setup(build) {
      build.onLoad({ filter: /\.(so|node)$/ }, args => {
        const bytes = readFileSync(args.path)
        if (bytes.length < 64 || !bytes.subarray(0, 7).equals(Buffer.from([127, 69, 76, 70, 2, 1, 1])) || bytes.readUInt16LE(18) !== 183)
          throw new Error("Expected ELF64 LE AArch64 native import: " + args.path)
        const hash = createHash("sha256").update(bytes).digest("hex")
        const physical = `libandcode-oc2-native-${hash.slice(0, 16)}.so`
        if (seen.has(physical) && seen.get(physical) !== hash) throw new Error("Native hash-prefix collision")
        seen.set(physical, hash)
        writeFileSync(path.join(stage, "native", physical), bytes, { mode: 0o755 })
        if (/[\t\r\n]/.test(args.path)) throw new Error("Invalid native import path")
        rows.add([physical, hash, bytes.length, args.path].join("\t"))
        writeFileSync(path.join(stage, "oc2-native.tsv"), [...rows].sort().join("\n") + "\n")
        const locate = `const d=process.env.ANDCODE_EXE_DIR; if(!d || !d.startsWith('/')) throw new Error('Missing absolute ANDCODE_EXE_DIR'); const p=d+${JSON.stringify("/" + physical)};`
        // .node imports export the addon, unlike FFI's .so file imports (paths).
        // Calling process.dlopen with a real path bypasses Bun's embedded extractor.
        const contents = args.path.endsWith(".node")
          ? `${locate} const m={exports:{}}; process.dlopen(m,p); module.exports=m.exports;`
          : `${locate} export default p;`
        return { loader: "js", contents }
      })
    },
  }
}
