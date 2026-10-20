import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
const projectDir = process.cwd();
const workspaceDir = "C:/Users/omres/.codex/visualizations/2026/10/18/01a14c94-7f48-71c1-8684-8be7326d7867";
const skillDir = "C:/Users/omres/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations";
const candidatePath = path.join(workspaceDir,".presentation-build","VadeX_Juri_Sunumu_TR.candidate.pptx");
const finalPath = path.join(workspaceDir,"presentation-output","VadeX_Juri_Sunumu_TR.validated.pptx");
const stagingDir = path.join(workspaceDir,".presentation-validation");
await fs.mkdir(stagingDir,{recursive:true});
await fs.mkdir(path.dirname(candidatePath),{recursive:true});
await fs.mkdir(path.dirname(finalPath),{recursive:true});
await fs.copyFile(path.join(projectDir,".presentation-build","candidate.pptx"),candidatePath);
const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir,"container_tools/artifact_tool_utils.mjs")).href);
const result = await finalizePresentation({
  explicitTotalSlideCount: 7,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: "C:/Users/omres/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
  integrityValidatorPath: path.join(skillDir,"container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir,"container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu","12192000,6858000","--validate-bullet-geometry","--validate-heading-fit"],
  fontPolicy: {basis:"design",families:["Segoe UI"]},
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir,"VadeX_Juri_Sunumu_TR.validation.json"),
});
console.log(JSON.stringify({result,validatedFile:finalPath},null,2));


