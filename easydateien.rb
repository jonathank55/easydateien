class Easydateien < Formula
  desc "Deutschsprachiger Terminaldateimanager für macOS mit integrierter Konsole"
  homepage "https://github.com/jonathank55/easydateien"
  url "https://github.com/jonathank55/easydateien/archive/refs/tags/v1.5.7.tar.gz"
  sha256 "19f0f13232d7c6bbca89362466a8d58aab4581bd7a0998557229a2d88c4c3c55"
  license "MIT"

  depends_on "python@3.12"

  def install
    libexec.install "easydateien",
                    "easydateien_actions.py",
                    "easydateien_clip.m",
                    "easydateien_common.py",
                    "easydateien_konfigurator.py",
                    "easydateien_pdf.m",
                    "easydateien_preview.py",
                    "easydateien_symlink.py",
                    "easydateien_ui.py",
                    "easydateien_view.py",
                    "config.json"

    (bin/"easydateien").write <<~EOS
      #!/usr/bin/env bash
      exec python3 "#{libexec}/easydateien" "$@"
    EOS
    chmod 0755, bin/"easydateien"
    bin.install_symlink bin/"easydateien" => "ed"
  end

  def caveats
    <<~EOS
      Hinweis: EasyDateien ist ein rein deutschsprachiges Programm.
      Konfiguration liegt unter ~/.config/easydateien/config.json.
      Startbefehle: 'easydateien' oder 'ed'.

      Automatischer Verzeichniswechsel beim Beenden:
      Füge Folgendes in deine ~/.zshrc (oder ~/.bashrc) ein:
        eval "$(easydateien --init zsh)"
    EOS
  end

  test do
    assert_predicate libexec/"easydateien", :executable?
    assert_path_exists libexec/"easydateien_common.py"
    assert_path_exists libexec/"easydateien_preview.py"
    assert_match "EasyDateien 1.5.7", shell_output("#{bin}/easydateien -v")
    assert_match "easydateien()", shell_output("#{bin}/easydateien --init zsh")
  end
end
