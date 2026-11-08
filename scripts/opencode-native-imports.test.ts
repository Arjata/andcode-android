import { test, expect } from "bun:test"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { nativeImports } from "./opencode-native-imports"

test("native imports become explicit runtime paths with byte-identical staged ELF", async () => {
  const root = mkdtempSync(path.join(tmpdir(), "andcode-native-imports-"))
  try {
    const elf = Buffer.alloc(64)
    Buffer.from([127, 69, 76, 70, 2, 1, 1]).copy(elf)
    elf.writeUInt16LE(183, 18)
    writeFileSync(path.join(root, "lib.so"), elf)
    writeFileSync(path.join(root, "binding.node"), elf)
    writeFileSync(path.join(root, "entry.ts"), 'import lib from "./lib.so" with {type:"file"}; import addon from "./binding.node"; const other=require("./binding.node"); const ffi=require("./lib.so"); if(addon.marker!==lib || other.marker!==lib || ffi!==lib) throw Error("native export mismatch"); console.log("NATIVE_IMPORT_OK")')
    const result = await Bun.build({ entrypoints: [path.join(root, "entry.ts")], target: "bun", plugins: [nativeImports(root)] })
    expect(result.success).toBe(true)
    const code = await result.outputs[0].text()
    expect(code).toContain("process.env.ANDCODE_EXE_DIR")
    expect(code).toMatch(/process\.dlopen\(m, p\d*\)/)
    expect(code).not.toContain("$bunfs")
    const rows = readFileSync(path.join(root, "oc2-native.tsv"), "utf8").trim().split("\n")
    expect(rows).toHaveLength(2)
    for (const row of rows) expect(readFileSync(path.join(root, "native", row.split("\t")[0]))).toEqual(elf)
    const output = path.join(root, "output.mjs")
    writeFileSync(output, code)
    const proc = Bun.spawn([process.execPath, "-e", `process.dlopen=(m,p)=>{m.exports={marker:p}}; await import(${JSON.stringify(pathToFileURL(output).href)})`], {env:{...process.env,ANDCODE_EXE_DIR:"/native"},stdout:"pipe",stderr:"pipe"})
    expect(await proc.exited).toBe(0)
    expect(await new Response(proc.stdout).text()).toContain("NATIVE_IMPORT_OK")
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test("persistent PTY binding requires an absolute preinstalled executable without embedding it", async () => {
  const root = mkdtempSync(path.join(tmpdir(), "andcode-native-imports-"))
  try {
    mkdirSync(path.join(root, "persistent-pty"))
    writeFileSync(path.join(root, "persistent-pty/pty-binding.ts"), 'throw Error("upstream embedded binary must not run")')
    writeFileSync(path.join(root, "entry.ts"), 'import p from "./persistent-pty/pty-binding"; console.log(p)')
    const result = await Bun.build({entrypoints:[path.join(root,"entry.ts")],target:"bun",plugins:[nativeImports(root)]})
    expect(result.success).toBe(true)
    const output = path.join(root, "output.mjs")
    const code = await result.outputs[0].text()
    expect(code).not.toContain("upstream embedded binary")
    expect(code).not.toContain("$bunfs")
    writeFileSync(output, code)
    for (const value of ["", "relative", "/native/libandcode-opencode-pty.so"]) {
      const proc=Bun.spawn([process.execPath,output],{env:{...process.env,OPENCODE_PTY_BIN:value},stdout:"pipe",stderr:"pipe"})
      expect(await proc.exited).toBe(value.startsWith("/")?0:1)
      if (value.startsWith("/")) expect(await new Response(proc.stdout).text()).toContain(value)
    }
  } finally { rmSync(root,{recursive:true,force:true}) }
})

test("wrong architecture and non-ELF imports fail closed", async () => {
  for (const bytes of [Buffer.from("not ELF"), (() => { const b = Buffer.alloc(64); Buffer.from([127,69,76,70,2,1,1]).copy(b); b.writeUInt16LE(62,18); return b })()]) {
    const root = mkdtempSync(path.join(tmpdir(), "andcode-native-imports-"))
    try {
      writeFileSync(path.join(root, "bad.so"), bytes)
      writeFileSync(path.join(root, "entry.ts"), 'import lib from "./bad.so" with {type:"file"}; console.log(lib)')
      let rejected = false
      try {
        const result = await Bun.build({ entrypoints: [path.join(root, "entry.ts")], target: "bun", plugins: [nativeImports(root)] })
        rejected = !result.success
      } catch { rejected = true }
      expect(rejected).toBe(true)
    } finally { rmSync(root, { recursive: true, force: true }) }
  }
})
