class Easydateien < Formula
  desc "Deutschsprachiger Terminal-Dateimanager für macOS mit integrierter Konsole"
  homepage "https://github.com/jonathank55/easydateien"
  url "https://github.com/jonathank55/easydateien/archive/refs/tags/v1.4.10.tar.gz"
  sha256 "167455239fcd561d478ed210148acaa49bdc81cc6afa2e7995330327afca4f59"
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
    EOS
  end

  test do
    assert_predicate libexec/"easydateien", :executable?
    assert_path_exists libexec/"easydateien_common.py"
    assert_match "EasyDateien 1.4.10", shell_output("#{bin}/easydateien -v")
  end
end
