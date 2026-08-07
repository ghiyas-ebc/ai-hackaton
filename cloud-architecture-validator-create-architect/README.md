# Packaging & installation

## What has to travel together

A skill is a **directory** whose root contains `SKILL.md`. Everything the skill
needs must sit inside that directory, referenced by relative path — nothing may
point outside it. That is the constraint the original draft broke: the Azure
skill referenced files inside the GCP skill's folder, so installing it alone
left it without its own workflow.

```
cloud-architecture-validator-create-architect/
├── SKILL.md                  <- required, must be at the root
├── README.md                 <- this file (not read by Claude at runtime)
├── references/               <- loaded into context only when needed
│   ├── gcp.md
│   ├── azure.md
│   ├── translation.md
│   ├── rendering.md
│   └── kg/*.yaml             <- the knowledge graph
├── scripts/*.py              <- executed, not loaded into context
└── evals/*.json              <- test material; harmless to ship
```

## Building the archive

Zip the directory itself, not its contents — the folder must be the top-level
entry inside the archive:

```bash
cd /path/containing/the/folder
rm -rf cloud-architecture-validator-create-architect/scripts/__pycache__
zip -r cloud-architecture-validator-create-architect.zip cloud-architecture-validator
```

Verify before uploading:

```bash
unzip -l cloud-architecture-validator-create-architect.zip | head
# the first paths must start with cloud-architecture-validator-create-architect/
```

Two things that quietly break an upload: zipping from inside the folder (so
`SKILL.md` lands at the archive root with no parent directory), and macOS
`__MACOSX/` and `.DS_Store` entries. Strip the latter with:

```bash
zip -r cloud-architecture-validator-create-architect.zip cloud-architecture-validator \
  -x "*.DS_Store" -x "__MACOSX/*"
```

The draft you sent had exactly this problem — `__MACOSX/` shadow entries plus
three byte-identical copies of the same SKILL.md.

## Installing

**claude.ai / Claude app.** Settings → Capabilities (or Features) → upload the
zip. <cite index="1-1">Custom Skills are uploaded as zip files through Settings, on Pro, Max, Team, and Enterprise plans with code execution enabled</cite>. <cite index="4-1">Each person uploads to their own account; on Team and Enterprise plans an organization owner can provision skills for everyone or enable sharing between colleagues</cite>.

**Claude Code.** No zip and no upload — <cite index="1-1">skills are filesystem-based: put the directory in `~/.claude/skills/` for personal use or `.claude/skills/` inside a repository for project use</cite>. This is the better setup while you are still iterating, because editing a YAML file and re-running `check_kg.py` takes seconds and needs no re-upload.

**Claude API.** <cite index="6-1">Upload the directory as a zip through the Skills API, which returns a skill ID to reference when attaching it to an agent</cite>. <cite index="2-1">This path requires the code execution tool plus the `skills-2025-10-02` and `files-api-2025-04-14` beta headers</cite>.

Since these details change, check https://support.claude.com/en/articles/12512180-use-skills-in-claude if anything does not match what you see.

## Dependency

The scripts need PyYAML, and nothing else — no cloud SDK, no credentials, no
network. If the runtime lacks it:

```bash
pip install pyyaml --break-system-packages
```

If you would rather remove the dependency entirely, convert
`references/kg/*.yaml` to JSON and swap `yaml.safe_load` for `json.load` in
`scripts/kg.py`. You lose comments, which is a real cost — most of the reasoning
behind the model lives in those comments.

## Keeping the service inventory current (`tools/`)

`tools/` is authoring machinery, not part of the shipped skill. Exclude it from
the upload zip — it needs network access and a Terraform binary, and the skill
itself must keep needing neither.

```bash
# on your machine, not in the skill runtime
mkdir -p /tmp/tfschema && cd /tmp/tfschema
cat > main.tf <<'TF'
terraform {
  required_providers {
    google  = { source = "hashicorp/google" }
    azurerm = { source = "hashicorp/azurerm" }
  }
}
TF
terraform init -backend=false
terraform providers schema -json > schema.json

# back in the skill directory
python3 tools/sync_provider_inventory.py --schema /tmp/tfschema/schema.json
```

This writes `tools/review_queue.yaml`: services that exist in the providers but
have no node in the KG, clustered into candidates, each carrying the four
classification questions that map onto the properties the rules read.

**The tool never writes `services.yaml`, and that restriction is deliberate.**
A missing node fails safely — the validator returns `UNKNOWN_SERVICE` and the
user is told to confirm. A node present with the wrong `reachability` fails
silently across roughly twenty pairs, producing confident wrong verdicts with
nothing to signal them. Provider schemas carry names and attributes; they do not
carry network placement, reachability, or roles. The fetch can be automated;
the classification cannot.

Workflow per accepted candidate:

1. Answer the questions in `review_queue.yaml`.
2. Add the node to `references/kg/services.yaml` by hand.
3. Register its prefix in `tools/resource-map.yaml` in the same commit —
   otherwise every future run reports it as new again.
4. Run `python3 scripts/check_kg.py`. Coverage must not drop.

Run this quarterly rather than continuously. Provider releases lag GA
announcements, preview features live in `google-beta`, and resource names follow
API naming rather than product naming — so this is a gap detector, not a source
of truth. `no_terraform_equivalent` in `resource-map.yaml` lists the KG nodes
that have no resource type at all, which is the standing reminder that Terraform
is an overlapping inventory rather than a superset.

## Before every release

```bash
python3 scripts/check_kg.py
```

It must report clean integrity, 37/37 regression, and coverage at or above 80%.
A drop in coverage means a rule became too narrow; do not ship it.

## Version control

Keep the directory in git and build the zip from a tag rather than editing
inside a zip. The knowledge graph is the asset here — the review history of
`references/kg/` is what makes it trustworthy over time, and that history is the
first thing lost when files are edited in place inside an archive.
