!define APPNAME "mozregression-gui"
!define COMPANYNAME "Mozilla"
!define DESCRIPTION "regression range finder for Mozilla nightly and integration builds"
# These three must be integers (not used yet)
!define VERSIONMAJOR 1
!define VERSIONMINOR 1
!define VERSIONBUILD 1
# These will be displayed by the "Click here for support information" link in "Add/Remove Programs"
# It is possible to use "mailto:" links in here to open the email client
!define HELPURL "http://mozilla.github.io/mozregression/" # "Support Information" link
!define UPDATEURL "https://github.com/mozilla/mozregression/releases" # "Product Updates" link
!define ABOUTURL "http://mozilla.github.io/mozregression/" # "Publisher" link
!define APPICON "app_icon.ico"
# This is the size (in kB) of all the files copied into "Program Files"
!define INSTALLSIZE 27756

# define name of installer
Name "${COMPANYNAME} - ${APPNAME}"
Icon "${APPICON}"
OutFile "${APPNAME}.exe"
 
# define installation directory
InstallDir "$PROGRAMFILES\${APPNAME}"

SetCompressor /SOLID lzma

RequestExecutionLevel highest

# start default section
Section
    # set the installation directory as the destination for the following actions
    SetOutPath "$INSTDIR"

    # copy files and icon
    createDirectory "$INSTDIR"
    File /r "..\dist\mozregression-gui\"
    File "${APPICON}"

    # create the uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    createDirectory "$SMPROGRAMS\${APPNAME}"
    # create shortcuts in the start menu programs directory
    CreateShortCut "$SMPROGRAMS\${APPNAME}\uninstall.lnk" "$INSTDIR\uninstall.exe"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe"

    # Registry information for add/remove programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayName" "${COMPANYNAME} - ${APPNAME} - ${DESCRIPTION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "InstallLocation" "$\"$INSTDIR$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayIcon" "$\"$INSTDIR\app_icon.ico$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "Publisher" "$\"${COMPANYNAME}$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "HelpLink" "$\"${HELPURL}$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLUpdateInfo" "$\"${UPDATEURL}$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLInfoAbout" "$\"${ABOUTURL}$\""
    #WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayVersion" "$\"${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}$\""
    #WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    #WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    # There is no option for modifying or repairing the install
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoRepair" 1
    # Set the INSTALLSIZE constant (!defined at the top of this script) so Add/Remove Programs can accurately report the size
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "EstimatedSize" ${INSTALLSIZE}
SectionEnd

# uninstaller section
Section "uninstall"
    Delete "$SMPROGRAMS\${APPNAME}\*.lnk"
    rmDir "$SMPROGRAMS\${APPNAME}"
    Delete "$INSTDIR\imageformats\*.*"
    rmDir "$INSTDIR\imageformats"
    Delete "$INSTDIR\*.*"
    rmDir "$INSTDIR"

    # Remove uninstaller information from the registry
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}"
SectionEnd