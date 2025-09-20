{ pkgs }: {
  deps = [
    pkgs.ffmpeg
    pkgs.tesseract
    pkgs.sqlite
    pkgs.python311Full
    pkgs.python311Packages.pip
    pkgs.python311Packages.flask
    pkgs.python311Packages.requests
  ];
}