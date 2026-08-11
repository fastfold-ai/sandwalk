import Foundation
import XCTest
@testable import SandwalkCore

final class SettingsSectionTests: XCTestCase {
    func testAllCasesHaveTitlesAndSymbols() {
        for section in SettingsSection.allCases {
            XCTAssertFalse(section.title.isEmpty, "\(section) title")
            XCTAssertFalse(section.symbol.isEmpty, "\(section) symbol")
            XCTAssertEqual(section.id, section.rawValue)
        }
    }

    func testFromDeepLinkSettingsHost() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/security")!),
            .security
        )
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/models")!),
            .models
        )
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/runtime")!),
            .runtime
        )
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/sandbox")!),
            .sandbox
        )
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://settings")!))
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/")!))
    }

    func testRuntimeSectionMetadata() {
        XCTAssertEqual(SettingsSection.runtime.title, "Runtime")
        XCTAssertEqual(SettingsSection.runtime.symbol, "cpu")
        XCTAssertEqual(SettingsSection.sandbox.title, "Sandbox")
        XCTAssertEqual(SettingsSection.sandbox.symbol, "shippingbox")
        XCTAssertEqual(SettingsSection.context.title, "Context")
        XCTAssertEqual(SettingsSection.context.symbol, "doc.text")
        XCTAssertEqual(SettingsSection.advanced.title, "Advanced")
        XCTAssertEqual(SettingsSection.advanced.symbol, "gearshape.2")
    }

    func testContextDeepLink() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/context")!),
            .context
        )
    }

    func testFromDeepLinkAdvanced() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/advanced")!),
            .advanced
        )
    }

    func testFromDeepLinkSectionAsHost() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://security")!),
            .security
        )
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://doctor")!),
            .doctor
        )
    }

    func testFromDeepLinkPathForms() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://host/settings/network")!),
            .network
        )
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://ignored/logs")!),
            .logs
        )
    }

    func testFromDeepLinkIsCaseInsensitive() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://Settings/Security")!),
            .security
        )
    }

    func testFromDeepLinkReturnsNilForUnknownSection() {
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/unknown")!))
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://not-a-section")!))
        // Desktop client routes must not parse as Settings sections.
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://open/agents/abc")!))
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://open/")!))
    }

    func testFromDeepLinkRejectsSectionHostWithExtraPath() {
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://security/extra")!))
    }

    func testGeneralSettingsSection() {
        XCTAssertEqual(SettingsSection.general.title, "Settings")
        XCTAssertEqual(SettingsSection.general.symbol, "gearshape")
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/general")!),
            .general
        )
    }
}
