#!/usr/bin/env bash
set -o pipefail

git config --global --add safe.directory /snowflake-cli

ROOT_DIR=$(git rev-parse --show-toplevel)
PACKAGING_DIR=$ROOT_DIR/scripts/packaging

SYSTEM=$(uname -s | tr '[:upper:]' '[:lower:]')
MACHINE=$(uname -m | tr '[:upper:]' '[:lower:]')

CLI_VERSION=$(hatch version)

DIST_DIR=$ROOT_DIR/dist
APP_NAME=SnowflakeCLI.app
APP_DIR=$DIST_DIR/app
APP_SCRIPTS=$DIST_DIR/scripts

loginfo() {
  logger -s -p INFO -- $1
}

loginfo "Building darwin package for version ${CLI_VERSION}"

rm -rf $APP_DIR || true
mkdir -p $APP_DIR || true
cd $APP_DIR

mkdir -p $APP_NAME/Contents/{MacOS,Resources}

cat >$APP_NAME/Contents/Info.plist <<INFO_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>SnowflakeCLI</string>
    <key>CFBundleDisplayName</key>
    <string>SnowflakeCLI</string>
    <key>CFBundleIdentifier</key>
    <string>net.snowflake.snowflake-cli</string>
    <key>CFBundleVersion</key>
    <string>$CLI_VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$CLI_VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>SnowflakeCLI.bash</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleSignature</key>
    <string>snow</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2016-2019 Snowflake, Inc. All rights reserved.</string>
    <key>CFBundleGetInfoString</key>
    <string>$CLI_VERSION Copyright © 2016-2019 Snowflake, Inc. All rights reserved.</string>
    <key>CFBundleIconFile</key>
    <string>SnowflakeCLI.icns</string>
</dict>
</plist>
INFO_PLIST

cp -r $DIST_DIR/snow $APP_NAME/Contents/MacOS/snow
cp -r $PACKAGING_DIR/macos/snowflake_darwin.icns $APP_NAME/Contents/Resources/SnowflakeCLI.icns
cp -r $PACKAGING_DIR/macos/SnowflakeCLI.bash $APP_NAME/Contents/MacOS/SnowflakeCLI.bash
chmod +x $APP_NAME/Contents/MacOS/SnowflakeCLI.bash

loginfo "---------------------------------"
security find-identity -v -p codesigning
loginfo "---------------------------------"

code_sign() {
  ENTITLEMENTS=$PACKAGING_DIR/macos/SnowflakeCLI_entitlements.plist
  loginfo "---------------------------------"
  loginfo "Code signing $1"
  loginfo "---------------------------------"
  codesign \
    --timestamp \
    --deep \
    --force \
    --entitlements $ENTITLEMENTS \
    --options=runtime \
    --sign "Developer ID Application: Snowflake Computing INC. (W4NT6CRQ7U)" \
    $1
}
code_sign_nrt() {
  ENTITLEMENTS=$PACKAGING_DIR/macos/SnowflakeCLI_entitlements.plist
  loginfo "---------------------------------"
  loginfo "Code signing $1 no runtime"
  loginfo "---------------------------------"
  codesign \
    --timestamp \
    --deep \
    --force \
    --entitlements $ENTITLEMENTS \
    --sign "Developer ID Application: Snowflake Computing INC. (W4NT6CRQ7U)" \
    $1 # --options=runtime \
}
code_sign_validate() {
  loginfo "---------------------------------"
  loginfo "Validating code signing for $1"
  loginfo "---------------------------------"
  codesign \
    -dvvv \
    --force \
   $1
}

APP_CONTENTS=$APP_NAME/Contents/MacOS/snow
ENTITLEMENTS=$PACKAGING_DIR/macos/SnowflakeCLI_entitlements.plist

code_sign $APP_CONTENTS
code_sign_validate $APP_CONTENTS

for l in $(find . -name '*.so'); do
  code_sign_nrt $l
  code_sign_validate $l
done

for l in $(find . -name '*.dylib'); do
  code_sign_nrt $l
  code_sign_validate $l
done


# POSTINSTALL SCRIPT
rm -rf $APP_SCRIPTS || true
mkdir -p $APP_SCRIPTS || true
cat >$APP_SCRIPTS/postinstall <<POSTINSTALL
#!/bin/bash -e
#
# $2 is the install location
#
SNOWFLAKE_CLI_COMMENT="# added by Snowflake SnowflakeCLI installer v1.2"

function add_dest_path_to_profile() {
    local dest=$1
    local profile=$2
    echo "Updating $profile to have $dest in PATH"
    touch $profile
    cp -p $profile "$profile-snowflake.bak" || true
    echo "
$SNOWFLAKE_CLI_COMMENT
export PATH=$dest:\$PATH" >> $profile
}

echo "[DEBUG] Parameters: $1 $2"
SNOWFLAKE_CLI_DEST=$2/${APP_NAME}/Contents/MacOS

SNOWFLAKE_CLI_LOGIN_SHELL=~/.profile
if [[ -e ~/.zprofile ]]; then
    SNOWFLAKE_CLI_LOGIN_SHELL=~/.zprofile
elif [[ -e ~/.zshrc ]]; then
    SNOWFLAKE_CLI_LOGIN_SHELL=~/.zshrc
elif [[ -e ~/.profile ]]; then
    SNOWFLAKE_CLI_LOGIN_SHELL=~/.profile
elif [[ -e ~/.bash_profile ]]; then
    SNOWFLAKE_CLI_LOGIN_SHELL=~/.bash_profile
elif [[ -e ~/.bashrc ]]; then
    SNOWFLAKE_CLI_LOGIN_SHELL=~/.bashrc
fi

if ! grep -q -E "^$SNOWFLAKE_CLI_COMMENT" $SNOWFLAKE_CLI_LOGIN_SHELL; then
    add_dest_path_to_profile $SNOWFLAKE_CLI_DEST $SNOWFLAKE_CLI_LOGIN_SHELL
fi
POSTINSTALL

ls -l $DIST_DIR

chmod +x $DIST_DIR/scripts/postinstall
loginfo "---------------------------------"
loginfo "Package build $DIST_DIR/snowflake-cli-${SYSTEM}.unsigned.pkg "
loginfo "---------------------------------"
pkgbuild \
  --identifier net.snowflake.snowflake-cli \
  --install-location '/Applications' \
  --version $CLI_VERSION \
  --scripts $APP_SCRIPTS \
  --root $APP_DIR \
  --component-plist $PACKAGING_DIR/macos/SnowflakeCLI.plist \
  $DIST_DIR/snowflake-cli-${SYSTEM}.unsigned.pkg

ls -l $DIST_DIR

loginfo "---------------------------------"
loginfo "Procuct sign $DIST_DIR/snowflake-cli-${SYSTEM}.unsigned.pkg -> $DIST_DIR/snowflake-cli-${SYSTEM}.pkg"
loginfo "---------------------------------"
productsign \
  --sign "Developer ID Installer: Snowflake Computing INC. (W4NT6CRQ7U)" \
  $DIST_DIR/snowflake-cli-${SYSTEM}.unsigned.pkg \
  $DIST_DIR/snowflake-cli-${SYSTEM}.pkg

ls -l $DIST_DIR

loginfo "---------------------------------"
loginfo "Procuct build $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.unsigned.pkg <- $DIST_DIR/snowflake-cli-${SYSTEM}.pkg"
loginfo "---------------------------------"
productbuild \
  --distribution $PACKAGING_DIR/macos/Distribution.xml \
  --version $CLI_VERSION \
  --resources $PACKAGING_DIR/macos/Resources \
  --package-path $DIST_DIR \
  $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.unsigned.pkg

ls -l $DIST_DIR

loginfo "---------------------------------"
loginfo "Procuct sign $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.unsigned.pkg -> $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.pkg"
loginfo "---------------------------------"
productsign \
  --sign "Developer ID Installer: Snowflake Computing INC. (W4NT6CRQ7U)" \
  $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.unsigned.pkg \
  $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.pkg

ls -l $DIST_DIR

cp -p \
  $DIST_DIR/snowflake-cli-${SYSTEM}-${MACHINE}.pkg \
  $DIST_DIR/snowflake-cli-${CLI_VERSION}-${SYSTEM}-${MACHINE}.pkg

ls -l $DIST_DIR