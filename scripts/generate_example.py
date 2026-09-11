#!/usr/bin/env python3
"""Generate only the bundled example project. Never run on a user's project."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "examples/HelloDevice"


class Ref(str):
    pass


def encode(value, indent=0):
    if isinstance(value, Ref):
        return value
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "(" + ", ".join(encode(v, indent) for v in value) + ("," if value else "") + ")"
    pad = "\t" * indent
    return "{\n" + "".join(pad + "\t" + k + " = " + encode(v, indent + 1) + ";\n" for k, v in value.items()) + pad + "}"


def generate():
    objects = {}

    def add(key, isa, **values):
        ref = Ref(hashlib.sha256(key.encode()).hexdigest()[:24].upper())
        objects[ref] = {"isa": isa, **values}
        return ref

    def configs(key, common):
        configurations = []
        for mode in ("Debug", "Release"):
            settings = dict(common)
            if mode == "Debug":
                settings.update(SWIFT_OPTIMIZATION_LEVEL="-Onone", SWIFT_ACTIVE_COMPILATION_CONDITIONS="DEBUG", DEBUG_INFORMATION_FORMAT="dwarf")
            else:
                settings.update(SWIFT_OPTIMIZATION_LEVEL="-O", SWIFT_COMPILATION_MODE="wholemodule")
            configurations.append(add(key + mode, "XCBuildConfiguration", name=mode, buildSettings=settings))
        return add(key, "XCConfigurationList", buildConfigurations=configurations, defaultConfigurationIsVisible=0, defaultConfigurationName="Release")

    source = add("source", "PBXFileReference", lastKnownFileType="sourcecode.swift", path="App/HelloDeviceApp.swift", sourceTree="<group>")
    build_file = add("build", "PBXBuildFile", fileRef=source)
    product = add("product", "PBXFileReference", explicitFileType="wrapper.application", path="HelloDevice.app", sourceTree="BUILT_PRODUCTS_DIR", includeInIndex=0)
    products = add("products", "PBXGroup", children=[product], name="Products", sourceTree="<group>")
    main = add("main", "PBXGroup", children=[source, products], sourceTree="<group>")
    phases = [add("sources", "PBXSourcesBuildPhase", buildActionMask=2147483647, files=[build_file], runOnlyForDeploymentPostprocessing=0),
              add("frameworks", "PBXFrameworksBuildPhase", buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0),
              add("resources", "PBXResourcesBuildPhase", buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)]
    project_configs = configs("project-config", {
        "CLANG_ENABLE_MODULES": "YES", "CLANG_ENABLE_OBJC_ARC": "YES", "SDKROOT": "iphoneos",
        "IPHONEOS_DEPLOYMENT_TARGET": "17.0", "SWIFT_VERSION": "5.0",
    })
    target_configs = configs("target-config", {
        "PRODUCT_NAME": "$(TARGET_NAME)", "PRODUCT_BUNDLE_IDENTIFIER": "org.example.HelloDevice",
        "CODE_SIGN_STYLE": "Automatic", "DEVELOPMENT_TEAM": "", "GENERATE_INFOPLIST_FILE": "YES",
        "INFOPLIST_KEY_CFBundleDisplayName": "HelloDevice", "INFOPLIST_KEY_LSApplicationCategoryType": "public.app-category.developer-tools",
        "INFOPLIST_KEY_UIApplicationSceneManifest_Generation": "YES", "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
        "INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone": "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight",
        "INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad": "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight",
        "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator", "TARGETED_DEVICE_FAMILY": "1,2", "SUPPORTS_MACCATALYST": "NO",
        "SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD": "NO", "MARKETING_VERSION": "0.1.0", "CURRENT_PROJECT_VERSION": "1",
        "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks"],
    })
    target = add("target", "PBXNativeTarget", buildConfigurationList=target_configs, buildPhases=phases, buildRules=[], dependencies=[],
                 name="HelloDevice", productName="HelloDevice", productReference=product, productType="com.apple.product-type.application")
    project = add("project", "PBXProject", attributes={"LastUpgradeCheck": "1500"}, buildConfigurationList=project_configs,
                  compatibilityVersion="Xcode 14.0", developmentRegion="en", knownRegions=["en", "ja", "Base"],
                  mainGroup=main, productRefGroup=products, projectDirPath="", projectRoot="", targets=[target])
    folder = ROOT / "HelloDevice.xcodeproj"
    schemes = folder / "xcshareddata/xcschemes"
    schemes.mkdir(parents=True, exist_ok=True)
    data = {"archiveVersion": 1, "classes": {}, "objectVersion": 56, "objects": objects, "rootObject": project}
    (folder / "project.pbxproj").write_text("// !$*UTF8*$!\n" + encode(data) + "\n", encoding="utf-8")
    buildable = ('<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="' + target +
                 '" BuildableName="HelloDevice.app" BlueprintName="HelloDevice" ReferencedContainer="container:HelloDevice.xcodeproj"/>')
    scheme = '''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1500" version="1.3">
  <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>
    <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">%s</BuildActionEntry>
  </BuildActionEntries></BuildAction>
  <TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES"><Testables/></TestAction>
  <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES">
    <BuildableProductRunnable runnableDebuggingMode="0">%s</BuildableProductRunnable>
  </LaunchAction>
  <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES">
    <BuildableProductRunnable runnableDebuggingMode="0">%s</BuildableProductRunnable>
  </ProfileAction>
  <AnalyzeAction buildConfiguration="Debug"/>
  <ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''' % (buildable, buildable, buildable)
    (schemes / "HelloDevice.xcscheme").write_text(scheme, encoding="utf-8")


if __name__ == "__main__":
    generate()
