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
        XCTAssertEqual(SettingsSection.prompts.title, "Prompts")
        XCTAssertEqual(SettingsSection.prompts.symbol, "text.alignleft")
        XCTAssertEqual(SettingsSection.advanced.title, "Advanced")
        XCTAssertEqual(SettingsSection.advanced.symbol, "gearshape.2")
    }

    func testPromptsDeepLink() {
        XCTAssertEqual(
            SettingsSection.fromDeepLink(URL(string: "sandwalk://settings/prompts")!),
            .prompts
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
    }

    func testFromDeepLinkRejectsSectionHostWithExtraPath() {
        XCTAssertNil(SettingsSection.fromDeepLink(URL(string: "sandwalk://security/extra")!))
    }
}
