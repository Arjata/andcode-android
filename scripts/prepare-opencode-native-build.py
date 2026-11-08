"""Wire our experimental plugin into exactly the reviewed upstream build."""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
script = root / 'packages/cli/script/build.ts'
text = script.read_text(encoding='utf-8')
anchors = ['import { $ } from "bun"', '      appAssetsPlugin,']
for anchor in anchors:
    if text.count(anchor) != 1:
        raise SystemExit('Upstream build anchor mismatch: ' + anchor)
text = text.replace(anchors[0], anchors[0] + '\nimport { nativeImports } from "./andcode-native-imports"')
text = text.replace(anchors[1], '      nativeImports(process.env.ANDCODE_NATIVE_STAGE!),\n' + anchors[1])
target = script.with_name('andcode-native-imports.ts')
if target.exists():
    raise SystemExit('Refusing overwrite: ' + str(target))
shutil.copyfile(Path(__file__).with_name('opencode-native-imports.ts'), target)
script.write_text(text, encoding='utf-8', newline='\n')
