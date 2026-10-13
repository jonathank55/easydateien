class Easydateien < Formula
  desc "Minimalistischer Terminal-Dateimanager für macOS mit integrierter Konsole"
  homepage "https://github.com/jonathank55/easydateien"
  url "https://github.com/jonathank55/easydateien.git",
      tag:      "v1.1.0",
      revision: "HIER_DEN_32_STELLIGEN_COMMIT_SHA_EINFUEGEN"
  version "1.1.0"
  license "MIT"

  depends_on "python@3.12"

  def install
    # Programmdateien gemeinsam in libexec, damit die Python-Importe
    # (easydateien_common, easydateien_konfigurator) aufgelöst werden koennen.
    libexec.install "easydateien", "easydateien_common.py", "easydateien_konfigurator.py"
    (bin/"easydateien").write <<~EOS
      #!/bin/bash
      exec python3 "#{libexec}/easydateien" "$@"
    EOS
    chmod 0755, bin/"easydateien"
    ln_s bin/"easydateien", bin/"ed"
  end

  def caveats
    <<~EOS
      Konfiguration liegt unter ~/.config/easydateien/config.json.
      Der native macOS-Clipboard-Helfer wird beim ersten Kopieren
      automatisch kompiliert (benötigt Xcode Command Line Tools).
    EOS
  end

  test do
    assert_predicate libexec/"easydateien", :executable?
    assert_predicate libexec/"easydateien_common.py", :exist?
  end
end
