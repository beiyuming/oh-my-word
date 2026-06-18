param(
    [string]$Name = "oh-my-word-py",
    [string]$InstallerName = "",
    [switch]$SkipPortableBuild
)

$ErrorActionPreference = "Stop"

function Get-AppVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$VersionFile
    )

    if (-not (Test-Path -LiteralPath $VersionFile)) {
        throw "Version file not found: $VersionFile"
    }

    $match = Select-String -LiteralPath $VersionFile -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        throw "APP_VERSION not found in $VersionFile"
    }
    return $match.Matches[0].Groups[1].Value
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$AppVersion = Get-AppVersion (Join-Path $projectRoot "app\version.py")
if ([string]::IsNullOrWhiteSpace($InstallerName)) {
    $InstallerName = "oh-my-word-setup-v$AppVersion.exe"
}
$portableDir = Join-Path $projectRoot "dist\$Name"
$distDir = Join-Path $projectRoot "dist"
$stagingDir = Join-Path ([System.IO.Path]::GetTempPath()) ("oh-my-word-installer-build-" + [System.Guid]::NewGuid().ToString("N"))
$payloadZipName = "$Name-portable.zip"
$payloadZipPath = Join-Path $stagingDir $payloadZipName
$sourcePath = Join-Path $stagingDir "InstallerProgram.cs"
$installerPath = Join-Path $distDir $InstallerName
$cscPath = "C:\WINDOWS\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path -LiteralPath $cscPath)) {
    $cscPath = "C:\WINDOWS\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path -LiteralPath $cscPath)) {
    throw "Could not find csc.exe."
}

if (-not $SkipPortableBuild) {
    & (Join-Path $PSScriptRoot "build_exe.ps1") -Name $Name
}

if (-not (Test-Path -LiteralPath $portableDir)) {
    throw "Portable build not found: $portableDir"
}

Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

if (Test-Path -LiteralPath $payloadZipPath) {
    Remove-Item -LiteralPath $payloadZipPath -Force
}
Compress-Archive -Path (Join-Path $portableDir "*") -DestinationPath $payloadZipPath -Force

$installerSource = @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        try
        {
            using (var form = new InstallerForm())
            {
                return form.ShowDialog() == DialogResult.OK ? 0 : 1;
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.ToString(),
                "Oh My Word Installer",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
    }

    private sealed class InstallerForm : Form
    {
        private readonly TextBox installPathBox;
        private readonly CheckBox desktopShortcutBox;
        private readonly CheckBox startMenuShortcutBox;
        private readonly CheckBox launchAfterInstallBox;
        private readonly Button installButton;
        private readonly ProgressBar progressBar;
        private readonly Label statusLabel;

        public InstallerForm()
        {
            Text = "Oh My Word Setup v$AppVersion";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ClientSize = new Size(620, 260);

            var defaultInstallRoot = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs",
                "Oh My Word");

            var titleLabel = new Label
            {
                Text = "Install Oh My Word v$AppVersion",
                AutoSize = true,
                Font = new Font(Font.FontFamily, 12f, FontStyle.Bold),
                Location = new Point(18, 18)
            };

            var descriptionLabel = new Label
            {
                Text = "Choose an install folder. Setup will extract app files and create shortcuts.",
                AutoSize = true,
                Location = new Point(20, 50)
            };

            var pathLabel = new Label
            {
                Text = "Install folder",
                AutoSize = true,
                Location = new Point(20, 86)
            };

            installPathBox = new TextBox
            {
                Text = defaultInstallRoot,
                Location = new Point(20, 108),
                Size = new Size(420, 24)
            };

            var browseButton = new Button
            {
                Text = "Browse...",
                Location = new Point(452, 106),
                Size = new Size(88, 28)
            };
            browseButton.Click += BrowseInstallPath;

            desktopShortcutBox = new CheckBox
            {
                Text = "Create desktop shortcut",
                Checked = true,
                AutoSize = true,
                Location = new Point(20, 146)
            };

            startMenuShortcutBox = new CheckBox
            {
                Text = "Create Start Menu shortcut",
                Checked = true,
                AutoSize = true,
                Location = new Point(190, 146)
            };

            launchAfterInstallBox = new CheckBox
            {
                Text = "Launch after install",
                Checked = true,
                AutoSize = true,
                Location = new Point(380, 146)
            };

            progressBar = new ProgressBar
            {
                Location = new Point(20, 182),
                Size = new Size(580, 18),
                Style = ProgressBarStyle.Continuous
            };

            statusLabel = new Label
            {
                Text = "",
                AutoSize = true,
                Location = new Point(20, 208)
            };

            installButton = new Button
            {
                Text = "Install",
                Location = new Point(420, 214),
                Size = new Size(84, 28)
            };
            installButton.Click += Install;

            var cancelButton = new Button
            {
                Text = "Cancel",
                DialogResult = DialogResult.Cancel,
                Location = new Point(516, 214),
                Size = new Size(84, 28)
            };

            Controls.AddRange(new Control[]
            {
                titleLabel,
                descriptionLabel,
                pathLabel,
                installPathBox,
                browseButton,
                desktopShortcutBox,
                startMenuShortcutBox,
                launchAfterInstallBox,
                progressBar,
                statusLabel,
                installButton,
                cancelButton
            });

            AcceptButton = installButton;
            CancelButton = cancelButton;
        }

        private void BrowseInstallPath(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Choose the Oh My Word install folder";
                dialog.SelectedPath = installPathBox.Text;
                dialog.ShowNewFolderButton = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    installPathBox.Text = dialog.SelectedPath;
                }
            }
        }

        private void Install(object sender, EventArgs e)
        {
            try
            {
                installButton.Enabled = false;
                UseWaitCursor = true;
                statusLabel.Text = "Installing...";
                progressBar.Value = 10;
                Application.DoEvents();

                var installRoot = NormalizeInstallRoot(installPathBox.Text);
                InstallPayload(
                    installRoot,
                    desktopShortcutBox.Checked,
                    startMenuShortcutBox.Checked,
                    launchAfterInstallBox.Checked);

                progressBar.Value = 100;
                statusLabel.Text = "Installation complete.";
                MessageBox.Show(
                    this,
                    "Oh My Word installation is complete.",
                    "Oh My Word",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
                DialogResult = DialogResult.OK;
                Close();
            }
            catch (Exception ex)
            {
                installButton.Enabled = true;
                MessageBox.Show(
                    this,
                    ex.ToString(),
                    "Oh My Word setup failed",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
            finally
            {
                UseWaitCursor = false;
            }
        }

        private void InstallPayload(
            string installRoot,
            bool createDesktopShortcut,
            bool createStartMenuShortcut,
            bool launchAfterInstall)
        {
            var startMenuDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Oh My Word");
            var desktopShortcut = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                "Oh My Word.lnk");
            var startMenuShortcut = Path.Combine(startMenuDir, "Oh My Word.lnk");
            var exePath = Path.Combine(installRoot, "oh-my-word-py.exe");
            var uninstallScript = Path.Combine(installRoot, "uninstall.ps1");
            var uninstallShortcut = Path.Combine(startMenuDir, "Uninstall Oh My Word.lnk");
            var manifestPath = Path.Combine(installRoot, "install_manifest.txt");

            Directory.CreateDirectory(installRoot);
            EnsureInstalledAppNotRunning(exePath);
            RemoveInstalledFilesFromManifest(installRoot, manifestPath);
            progressBar.Value = 25;
            Application.DoEvents();

            List<string> payloadFiles;
            var tempZip = Path.Combine(Path.GetTempPath(), "oh-my-word-installer-" + Guid.NewGuid().ToString("N") + ".zip");
            try
            {
                using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
                {
                    if (stream == null)
                    {
                        throw new InvalidOperationException("Installer payload resource missing.");
                    }

                    using (var output = File.Create(tempZip))
                    {
                        stream.CopyTo(output);
                    }
                }

                payloadFiles = ExtractZipToDirectory(tempZip, installRoot);
            }
            finally
            {
                if (File.Exists(tempZip))
                {
                    File.Delete(tempZip);
                }
            }
            progressBar.Value = 65;
            Application.DoEvents();

            if (!File.Exists(exePath))
            {
                throw new FileNotFoundException("Installed executable missing.", exePath);
            }

            WriteUninstallScript(
                uninstallScript,
                installRoot,
                startMenuDir,
                desktopShortcut,
                startMenuShortcut,
                uninstallShortcut,
                manifestPath);
            WriteInstallManifest(manifestPath, payloadFiles);

            if (createStartMenuShortcut)
            {
                Directory.CreateDirectory(startMenuDir);
                CreateShortcut(startMenuShortcut, exePath, installRoot);
                CreateShortcut(
                    uninstallShortcut,
                    "powershell.exe",
                    installRoot,
                    "-ExecutionPolicy Bypass -File \"" + uninstallScript + "\"");
            }

            if (createDesktopShortcut)
            {
                CreateShortcut(desktopShortcut, exePath, installRoot);
            }

            progressBar.Value = 85;
            Application.DoEvents();
            if (launchAfterInstall)
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = exePath,
                    WorkingDirectory = installRoot,
                    UseShellExecute = true
                });
            }
        }

    }

    private static string NormalizeInstallRoot(string rawPath)
    {
        if (string.IsNullOrWhiteSpace(rawPath))
        {
            throw new InvalidOperationException("Choose an install folder.");
        }

        var fullPath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(rawPath.Trim()));
        var root = Path.GetPathRoot(fullPath);
        if (string.IsNullOrEmpty(root))
        {
            throw new InvalidOperationException("Install folder is not a valid absolute path.");
        }
        if (string.Equals(fullPath.TrimEnd(Path.DirectorySeparatorChar), root.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Cannot install to a drive root.");
        }
        return fullPath;
    }

    private static void EnsureInstalledAppNotRunning(string exePath)
    {
        if (!File.Exists(exePath))
        {
            return;
        }

        var targetPath = Path.GetFullPath(exePath);
        var processName = Path.GetFileNameWithoutExtension(targetPath);
        foreach (var process in Process.GetProcessesByName(processName))
        {
            using (process)
            {
                string processPath;
                try
                {
                    processPath = process.MainModule.FileName;
                }
                catch
                {
                    continue;
                }

                if (string.Equals(Path.GetFullPath(processPath), targetPath, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException(
                        "Close Oh My Word before installing or updating. The installed app is still running: " + targetPath);
                }
            }
        }
    }

    private static List<string> ExtractZipToDirectory(string zipPath, string installRoot)
    {
        var installedFiles = new List<string>();
        using (var archive = ZipFile.OpenRead(zipPath))
        {
            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.FullName))
                {
                    continue;
                }

                var relativePath = entry.FullName.Replace('\\', '/').TrimStart('/');
                if (string.IsNullOrEmpty(relativePath))
                {
                    continue;
                }

                var destinationPath = CombineInsideRoot(installRoot, relativePath);
                if (string.IsNullOrEmpty(entry.Name))
                {
                    Directory.CreateDirectory(destinationPath);
                    continue;
                }

                var destinationDir = Path.GetDirectoryName(destinationPath);
                if (!Directory.Exists(destinationDir))
                {
                    Directory.CreateDirectory(destinationDir);
                }

                using (var input = entry.Open())
                using (var output = File.Create(destinationPath))
                {
                    input.CopyTo(output);
                }
                installedFiles.Add(relativePath);
            }
        }

        return installedFiles;
    }

    private static void RemoveInstalledFilesFromManifest(string installRoot, string manifestPath)
    {
        if (!File.Exists(manifestPath))
        {
            return;
        }

        foreach (var line in File.ReadAllLines(manifestPath))
        {
            var relativePath = line.Trim();
            if (string.IsNullOrEmpty(relativePath) || relativePath.StartsWith("#"))
            {
                continue;
            }

            var targetPath = CombineInsideRoot(installRoot, relativePath);
            if (File.Exists(targetPath))
            {
                File.Delete(targetPath);
            }
        }

        RemoveEmptyDirectories(installRoot, false);
    }

    private static void WriteInstallManifest(string manifestPath, List<string> payloadFiles)
    {
        var manifestEntries = new List<string>(payloadFiles);
        manifestEntries.Add("install_manifest.txt");
        File.WriteAllLines(manifestPath, manifestEntries.ToArray());
    }

    private static string CombineInsideRoot(string installRoot, string relativePath)
    {
        var rootFull = Path.GetFullPath(installRoot);
        if (!rootFull.EndsWith(Path.DirectorySeparatorChar.ToString()))
        {
            rootFull += Path.DirectorySeparatorChar;
        }

        var normalizedRelative = relativePath
            .Replace('/', Path.DirectorySeparatorChar)
            .Replace('\\', Path.DirectorySeparatorChar);
        var fullPath = Path.GetFullPath(Path.Combine(rootFull, normalizedRelative));
        if (!fullPath.StartsWith(rootFull, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Installer payload contains an unsafe path: " + relativePath);
        }
        return fullPath;
    }

    private static void RemoveEmptyDirectories(string rootPath, bool removeRoot)
    {
        if (!Directory.Exists(rootPath))
        {
            return;
        }

        var directories = Directory.GetDirectories(rootPath, "*", SearchOption.AllDirectories);
        Array.Sort(directories, (left, right) => right.Length.CompareTo(left.Length));
        foreach (var directory in directories)
        {
            if (Directory.Exists(directory) && Directory.GetFileSystemEntries(directory).Length == 0)
            {
                Directory.Delete(directory);
            }
        }

        if (removeRoot && Directory.Exists(rootPath) && Directory.GetFileSystemEntries(rootPath).Length == 0)
        {
            Directory.Delete(rootPath);
        }
    }

    private static void WriteUninstallScript(
        string scriptPath,
        string installRoot,
        string startMenuDir,
        string desktopShortcut,
        string startMenuShortcut,
        string uninstallShortcut,
        string manifestPath)
    {
        var script = string.Join(Environment.NewLine, new[]
        {
            "`$ErrorActionPreference = 'Stop'",
            "`$installRoot = '" + EscapePowerShell(installRoot) + "'",
            "`$manifestPath = '" + EscapePowerShell(manifestPath) + "'",
            "`$startMenuDir = '" + EscapePowerShell(startMenuDir) + "'",
            "`$desktopShortcut = '" + EscapePowerShell(desktopShortcut) + "'",
            "`$startMenuShortcut = '" + EscapePowerShell(startMenuShortcut) + "'",
            "`$uninstallShortcut = '" + EscapePowerShell(uninstallShortcut) + "'",
            "if (Test-Path -LiteralPath `$desktopShortcut) { Remove-Item -LiteralPath `$desktopShortcut -Force }",
            "if (Test-Path -LiteralPath `$startMenuShortcut) { Remove-Item -LiteralPath `$startMenuShortcut -Force }",
            "if (Test-Path -LiteralPath `$uninstallShortcut) { Remove-Item -LiteralPath `$uninstallShortcut -Force }",
            "if (Test-Path -LiteralPath `$startMenuDir) {",
            "    if (-not (Get-ChildItem -LiteralPath `$startMenuDir -Force | Select-Object -First 1)) {",
            "        Remove-Item -LiteralPath `$startMenuDir -Force",
            "    }",
            "}",
            "if (Test-Path -LiteralPath `$manifestPath) {",
            "    `$rootFull = [System.IO.Path]::GetFullPath(`$installRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar)",
            "    `$entries = Get-Content -LiteralPath `$manifestPath",
            "    foreach (`$entry in `$entries) {",
            "        if ([string]::IsNullOrWhiteSpace(`$entry) -or `$entry.TrimStart().StartsWith('#')) { continue }",
            "        `$targetPath = Join-Path `$installRoot `$entry",
            "        `$targetFull = [System.IO.Path]::GetFullPath(`$targetPath)",
            "        if (`$targetFull.StartsWith(`$rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath `$targetFull -PathType Leaf)) {",
            "            Remove-Item -LiteralPath `$targetFull -Force",
            "        }",
            "    }",
            "}",
            "if (`$PSCommandPath -and (Test-Path -LiteralPath `$PSCommandPath)) { Remove-Item -LiteralPath `$PSCommandPath -Force -ErrorAction SilentlyContinue }",
            "if (Test-Path -LiteralPath `$installRoot) {",
            "    Get-ChildItem -LiteralPath `$installRoot -Directory -Recurse -Force | Sort-Object { `$_.FullName.Length } -Descending | ForEach-Object {",
            "        if (-not (Get-ChildItem -LiteralPath `$_.FullName -Force | Select-Object -First 1)) { Remove-Item -LiteralPath `$_.FullName -Force }",
            "    }",
            "    if (-not (Get-ChildItem -LiteralPath `$installRoot -Force | Select-Object -First 1)) { Remove-Item -LiteralPath `$installRoot -Force }",
            "}",
            ""
        });
        File.WriteAllText(scriptPath, script);
    }

    private static void CreateShortcut(string shortcutPath, string targetPath, string workingDirectory)
    {
        CreateShortcut(shortcutPath, targetPath, workingDirectory, null);
    }

    private static void CreateShortcut(string shortcutPath, string targetPath, string workingDirectory, string arguments)
    {
        var shortcutDir = Path.GetDirectoryName(shortcutPath);
        if (!Directory.Exists(shortcutDir))
        {
            Directory.CreateDirectory(shortcutDir);
        }

        var shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null)
        {
            throw new InvalidOperationException("WScript.Shell is unavailable.");
        }

        dynamic shell = Activator.CreateInstance(shellType);
        dynamic shortcut = shell.CreateShortcut(shortcutPath);
        shortcut.TargetPath = targetPath;
        shortcut.WorkingDirectory = workingDirectory;
        if (!string.IsNullOrEmpty(arguments))
        {
            shortcut.Arguments = arguments;
        }
        shortcut.IconLocation = targetPath.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)
            ? targetPath + ",0"
            : targetPath;
        shortcut.Save();
    }

    private static string EscapePowerShell(string value)
    {
        return value.Replace("'", "''");
    }

}
"@
Set-Content -LiteralPath $sourcePath -Value $installerSource -Encoding UTF8

if (Test-Path -LiteralPath $installerPath) {
    Remove-Item -LiteralPath $installerPath -Force
}

$cscArgs = @(
    "/nologo",
    "/target:winexe",
    "/out:$installerPath",
    "/resource:$payloadZipPath,payload.zip",
    "/reference:System.dll",
    "/reference:System.Core.dll",
    "/reference:System.IO.Compression.dll",
    "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Drawing.dll",
    "/reference:System.Windows.Forms.dll",
    "/reference:Microsoft.CSharp.dll",
    $sourcePath
)

& $cscPath @cscArgs

if (-not (Test-Path -LiteralPath $installerPath)) {
    throw "Installer build failed: $installerPath"
}

Write-Output "Installer created: $installerPath"
Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
