{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
  let
    pkgs = nixpkgs.legacyPackages.x86_64-linux;
  in {
    devShells."x86_64-linux".default = pkgs.mkShellNoCC {
      packages = [
        pkgs.arduino-ide
        (pkgs.python3.withPackages (python-pkgs: [
          python-pkgs.paho-mqtt
          python-pkgs.cbor2
        ]))

        pkgs.mosquitto
      ];
    };
  };
}
