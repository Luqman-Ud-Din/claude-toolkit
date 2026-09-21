# Licence discovery commands per ecosystem

`scripts/license_inventory.py` works offline from manifests and local caches and marks
anything it cannot resolve as **unknown**. These commands fill the gaps with the
ecosystem's own tooling (they may need network access and a restore/install first).
Save the output under `audit/evidence/audit-licensing-and-compliance/` and re-run the
inventory, or paste the resolved licence into the finding's evidence.

## .NET / NuGet

```bash
# Offline: nuspec in the local cache (what the script reads)
ls ~/.nuget/packages/<id-lowercase>/<version>/*.nuspec
grep -iE "<license|<licenseUrl" ~/.nuget/packages/newtonsoft.json/13.0.3/newtonsoft.json.nuspec

# Full tree with licences (needs a restore)
dotnet tool install --global dotnet-project-licenses
dotnet-project-licenses -i Ibs.Inventory.sln -o -j --outfile licenses.json --include-transitive
# or per project, Markdown for the notices file:
dotnet-project-licenses -i Product.MicroAPI/Product.MicroAPI.csproj -m -o

# Registry lookup for one package
curl -s https://api.nuget.org/v3/registration5-gz-semver2/<id-lowercase>/index.json | gzip -dc | grep -o '"licenseExpression":"[^"]*"'
```

Direct `<Reference>`/`<HintPath>` DLLs have no metadata: open the vendor's site or the
DLL's embedded `AssemblyCopyright`/`AssemblyInformationalVersion` attributes.

## Java / Maven / Gradle

```bash
# Offline: the artifact's own POM in the local repo (what the script reads)
grep -A3 "<licenses>" ~/.m2/repository/<group/path>/<artifact>/<version>/<artifact>-<version>.pom

# Full tree with licences (network)
mvn org.codehaus.mojo:license-maven-plugin:add-third-party -Dlicense.excludedScopes=test
cat target/generated-sources/license/THIRD-PARTY.txt
# Aggregate for multi-module builds
mvn license:aggregate-add-third-party

# Gradle
./gradlew dependencies --configuration runtimeClasspath
# with the gradle-license-report plugin: ./gradlew generateLicenseReport -> build/reports/dependency-license/
```

Licences often live in the *parent* POM; the script only reads the artifact POM, so
"not in maven cache" frequently means "check the parent".

## Node / npm / pnpm / yarn

```bash
# Offline: what the script reads
node -e "console.log(require('./node_modules/<pkg>/package.json').license)"
grep -A2 '"node_modules/<pkg>"' package-lock.json      # lockfile v2/v3 carries "license"

# Full tree
npx license-checker --production --json --out licenses.json
npx license-checker --production --onlyAllow "MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;Unlicense"
npx license-checker --production --failOn "AGPL-3.0;GPL-3.0;GPL-2.0;SSPL-1.0"
pnpm licenses list --prod --json
yarn licenses list --production --json
npm view <pkg> license repository.url
```

`UNLICENSED`, `SEE LICENSE IN <file>` and missing `license` fields are all **unknown**
until a human reads the referenced file.

## Python / pip

```bash
# Offline: what the script reads
grep -E "^(License|Classifier: License)" .venv/lib/python*/site-packages/<pkg>-*.dist-info/METADATA

# Full environment
pip install pip-licenses
pip-licenses --format=json --with-urls --with-license-file --no-license-path > licenses.json
pip-licenses --format=markdown --with-authors            # notices-ready table
pip-licenses --fail-on "GNU General Public License v3 (GPLv3);GNU Affero General Public License v3"
# Single package from PyPI
curl -s https://pypi.org/pypi/<pkg>/json | python -c "import json,sys; d=json.load(sys.stdin)['info']; print(d['license'], [c for c in d['classifiers'] if c.startswith('License')])"
```

Many packages leave `License:` as `UNKNOWN` and only set the classifier; the script reads
both, but binary wheels compiled against GPL libraries (mysqlclient, pyqt) carry the
library's licence even when the wheel says otherwise.

## Container images

```bash
# Labels declared by the image author (OCI annotation)
docker inspect --format '{{json .Config.Labels}}' mcr.microsoft.com/dotnet/aspnet:10.0 | jq .
# org.opencontainers.image.licenses, org.opencontainers.image.source

# OS packages inside the image (Debian/Ubuntu based)
docker run --rm --entrypoint sh <image> -c "cat /usr/share/doc/*/copyright | grep -E '^License:' | sort | uniq -c"
# Alpine
docker run --rm --entrypoint sh <image> -c "apk info -a 2>/dev/null | grep -A1 license"
# SBOM route (any image)
syft <image> -o spdx-json > image-sbom.json      # or: docker sbom <image>
```

Base image licences rarely block a proprietary product (Debian/Alpine/MCR images are
permissively licensed as aggregates), but GPL *tools* inside the image are fine to run
and not fine to copy into your own binary.

## Fonts, icons, media, CDN scripts

Not in any package manager. Check the file's own licence: Google Fonts (OFL-1.1 - ship
the licence text), Font Awesome Free (OFL + CC-BY-4.0 for icons - attribution
required), Material Icons (Apache-2.0), Ionicons (MIT), stock images (usually
non-transferable - keep the receipt). CDN-loaded scripts (`<script src="https://...">`)
are covered by that provider's terms of service, not a package licence.

## SBOM as the durable artefact

Whichever ecosystem, an SPDX or CycloneDX SBOM is the format procurement and customers
ask for: `syft dir:. -o spdx-json`, `dotnet CycloneDX <sln>`, `cyclonedx-npm`,
`cyclonedx-py`, `mvn org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom`. Attach it in
`audit/evidence/audit-licensing-and-compliance/`.
