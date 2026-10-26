class Easydateien < Formula
  desc "Deutschsprachiger Terminal-Dateimanager für macOS mit integrierter Konsole"
  homepage "https://github.com/jonathank55/easydateien"
  url "https://github.com/jonathank55/easydateien/archive/refs/tags/v1.4.11.tar.gz"
  sha256 "637463580c9e4ba7b642d5a0b4c0988ef14997786aca40720d1fb0090bf84980"
  license "MIT"

  depends_on "python@3.12"

  def install
    libexec.install "easydateien",
                    "easydateien_actions.py",
                    "easydateien_clip.m",
                    "easydateien_common.py",
                    "easydateien_konfigurator.py",
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
    assert_match "EasyDateien 1.4.11", shell_output("#{bin}/easydateien -v")
    assert_match "easydateien()", shell_output("#{bin}/easydateien --init zsh")
  end
end
