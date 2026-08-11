import SwiftUI

struct SandboxSettingsNumberField: View {
    @Binding var value: Int
    var width: CGFloat = 72
    @Environment(\.sandwalkTheme) private var theme

    var body: some View {
        TextField("", value: $value, format: .number.grouping(.never))
            .font(.sandwalkMono(13))
            .multilineTextAlignment(.trailing)
            .textFieldStyle(.plain)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .frame(width: width)
            .background(theme.inputBg)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .strokeBorder(theme.inputBorder, lineWidth: 0.5)
            )
    }
}
