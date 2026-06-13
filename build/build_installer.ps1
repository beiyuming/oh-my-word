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
$voxcpmServiceDir = Join-Path $projectRoot "tools\voxcpm_service"
$voxcpmServiceZipPath = Join-Path $stagingDir "voxcpm_service.zip"
$voxcpmServicePayloadFiles = @(
    "install_local.ps1",
    "server.py",
    "engine.py",
    "requirements.txt",
    "README.md"
)
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

if (-not (Test-Path -LiteralPath (Join-Path $voxcpmServiceDir "install_local.ps1"))) {
    throw "VoxCPM local setup script not found: $voxcpmServiceDir"
}
$voxcpmServicePayloadPaths = foreach ($payloadFile in $voxcpmServicePayloadFiles) {
    $payloadPath = Join-Path $voxcpmServiceDir $payloadFile
    if (-not (Test-Path -LiteralPath $payloadPath)) {
        throw "VoxCPM service payload file not found: $payloadPath"
    }
    $payloadPath
}
Compress-Archive -Path $voxcpmServicePayloadPaths -DestinationPath $voxcpmServiceZipPath -Force

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
        private readonly TextBox voxCpmInstallPathBox;
        private readonly TextBox voxcpmModelCachePathBox;
        private readonly CheckBox desktopShortcutBox;
        private readonly CheckBox startMenuShortcutBox;
        private readonly CheckBox launchAfterInstallBox;
        private readonly CheckBox installVoxCpmBox;
        private readonly CheckBox useHfMirrorBox;
        private readonly Button installButton;
        private readonly ProgressBar progressBar;
        private readonly Label statusLabel;
        private bool updatingVoxCpmDefaults;
        private bool voxCpmInstallPathEdited;
        private bool voxCpmModelCachePathEdited;

        public InstallerForm()
        {
            Text = "Oh My Word Setup v$AppVersion";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ClientSize = new Size(620, 460);

            var defaultInstallRoot = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs",
                "Oh My Word");
            var defaultVoxCpmInstallRoot = Path.Combine(defaultInstallRoot, "tts", "voxcpm");
            var defaultVoxCpmModelCacheRoot = Path.Combine(defaultVoxCpmInstallRoot, "models");

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
            installPathBox.TextChanged += delegate(object textSender, EventArgs textArgs)
            {
                UpdateVoxCpmDefaultPathsFromInstallRoot();
            };

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

            installVoxCpmBox = new CheckBox
            {
                Text = "Install local VoxCPM pronunciation engine",
                Checked = false,
                AutoSize = true,
                Location = new Point(20, 176)
            };
            installVoxCpmBox.CheckedChanged += ToggleVoxCpmPathControls;

            var voxCpmInstallPathLabel = new Label
            {
                Text = "VoxCPM engine folder",
                AutoSize = true,
                Location = new Point(38, 204)
            };

            voxCpmInstallPathBox = new TextBox
            {
                Text = defaultVoxCpmInstallRoot,
                Location = new Point(38, 226),
                Size = new Size(402, 24)
            };
            voxCpmInstallPathBox.TextChanged += delegate(object textSender, EventArgs textArgs)
            {
                if (!updatingVoxCpmDefaults)
                {
                    voxCpmInstallPathEdited = true;
                }
            };

            var browseVoxCpmInstallButton = new Button
            {
                Text = "Browse...",
                Location = new Point(452, 224),
                Size = new Size(88, 28)
            };
            voxcpmModelCachePathBox.TextChanged += delegate(object textSender, EventArgs textArgs)
            {
                if (!updatingVoxCpmDefaults)
                {
                    voxCpmModelCachePathEdited = true;
                }
            };
            browseVoxCpmInstallButton.Click += BrowseVoxCpmInstallPath;

            var voxCpmModelCachePathLabel = new Label
            {
                Text = "VoxCPM model cache folder",
                AutoSize = true,
                Location = new Point(38, 258)
            };

            voxcpmModelCachePathBox = new TextBox
            {
                Text = defaultVoxCpmModelCacheRoot,
                Location = new Point(38, 280),
                Size = new Size(402, 24)
            };

            var browseVoxCpmModelCacheButton = new Button
            {
                Text = "Browse...",
                Location = new Point(452, 278),
                Size = new Size(88, 28)
            };
            browseVoxCpmModelCacheButton.Click += BrowseVoxCpmModelCachePath;

            useHfMirrorBox = new CheckBox
            {
                Text = "Use model download mirror (ModelScope first, hf-mirror fallback)",
                Checked = true,
                AutoSize = true,
                Location = new Point(38, 314)
            };

            var voxCpmDescriptionLabel = new Label
            {
                Text = "Optional. Downloads several GB and works best with NVIDIA GPU 8 GB+ VRAM. App installation completed even if VoxCPM setup fails.",
                AutoSize = false,
                Location = new Point(38, 342),
                Size = new Size(560, 36)
            };

            progressBar = new ProgressBar
            {
                Location = new Point(20, 386),
                Size = new Size(580, 18),
                Style = ProgressBarStyle.Continuous
            };

            statusLabel = new Label
            {
                Text = "",
                AutoSize = true,
                Location = new Point(20, 412)
            };

            installButton = new Button
            {
                Text = "Install",
                Location = new Point(420, 424),
                Size = new Size(84, 28)
            };
            installButton.Click += Install;

            var cancelButton = new Button
            {
                Text = "Cancel",
                DialogResult = DialogResult.Cancel,
                Location = new Point(516, 424),
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
                installVoxCpmBox,
                voxCpmInstallPathLabel,
                voxCpmInstallPathBox,
                browseVoxCpmInstallButton,
                voxCpmModelCachePathLabel,
                voxcpmModelCachePathBox,
                browseVoxCpmModelCacheButton,
                useHfMirrorBox,
                voxCpmDescriptionLabel,
                progressBar,
                statusLabel,
                installButton,
                cancelButton
            });

            AcceptButton = installButton;
            CancelButton = cancelButton;
            ToggleVoxCpmPathControls(null, EventArgs.Empty);
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

        private void UpdateVoxCpmDefaultPathsFromInstallRoot()
        {
            if (string.IsNullOrWhiteSpace(installPathBox.Text))
            {
                return;
            }

            try
            {
                updatingVoxCpmDefaults = true;
                var installRoot = Path.GetFullPath(Environment.ExpandEnvironmentVariables(installPathBox.Text.Trim()));
                var defaultVoxCpmInstallRoot = Path.Combine(installRoot, "tts", "voxcpm");
                if (!voxCpmInstallPathEdited)
                {
                    voxCpmInstallPathBox.Text = defaultVoxCpmInstallRoot;
                }
                if (!voxCpmModelCachePathEdited)
                {
                    voxcpmModelCachePathBox.Text = Path.Combine(defaultVoxCpmInstallRoot, "models");
                }
            }
            catch
            {
            }
            finally
            {
                updatingVoxCpmDefaults = false;
            }
        }

        private void BrowseVoxCpmInstallPath(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Choose the VoxCPM engine folder";
                dialog.SelectedPath = voxCpmInstallPathBox.Text;
                dialog.ShowNewFolderButton = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    voxCpmInstallPathEdited = true;
                    voxCpmInstallPathBox.Text = dialog.SelectedPath;
                    if (!voxCpmModelCachePathEdited)
                    {
                        voxcpmModelCachePathBox.Text = Path.Combine(dialog.SelectedPath, "models");
                    }
                }
            }
        }

        private void BrowseVoxCpmModelCachePath(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Choose the VoxCPM model cache folder";
                dialog.SelectedPath = voxcpmModelCachePathBox.Text;
                dialog.ShowNewFolderButton = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    voxCpmModelCachePathEdited = true;
                    voxcpmModelCachePathBox.Text = dialog.SelectedPath;
                }
            }
        }

        private void ToggleVoxCpmPathControls(object sender, EventArgs e)
        {
            voxCpmInstallPathBox.Enabled = installVoxCpmBox.Checked;
            voxcpmModelCachePathBox.Enabled = installVoxCpmBox.Checked;
            useHfMirrorBox.Enabled = installVoxCpmBox.Checked;
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
                var voxCpmInstallRoot = installVoxCpmBox.Checked
                    ? NormalizeVoxCpmInstallRoot(voxCpmInstallPathBox.Text)
                    : null;
                var voxCpmModelCacheRoot = installVoxCpmBox.Checked
                    ? NormalizeVoxCpmModelCacheRoot(voxcpmModelCachePathBox.Text)
                    : null;
                InstallPayload(
                    installRoot,
                    desktopShortcutBox.Checked,
                    startMenuShortcutBox.Checked,
                    launchAfterInstallBox.Checked,
                    installVoxCpmBox.Checked,
                    voxCpmInstallRoot,
                    voxCpmModelCacheRoot,
                    useHfMirrorBox.Checked);

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
            bool launchAfterInstall,
            bool installVoxCpmLocal,
            string voxCpmInstallRoot,
            string voxCpmModelCacheRoot,
            bool useHfMirror)
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

            if (installVoxCpmLocal)
            {
                statusLabel.Text = "Starting optional VoxCPM local setup...";
                Application.DoEvents();
                RunVoxCpmSetup(voxCpmInstallRoot, voxCpmModelCacheRoot, useHfMirror);
            }

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

        private void RunVoxCpmSetup(string voxCpmInstallRoot, string voxCpmModelCacheRoot, bool useHfMirror)
        {
            var tempDir = Path.Combine(Path.GetTempPath(), "oh-my-word-voxcpm-" + Guid.NewGuid().ToString("N"));
            var tempZip = Path.Combine(tempDir, "voxcpm_service.zip");
            var logPath = Path.Combine(voxCpmInstallRoot, "install.log");
            var bootstrapLogPath = Path.Combine(voxCpmInstallRoot, "install-bootstrap.log");

            try
            {
                EnsureVoxCpmSetupDirectories(voxCpmInstallRoot, voxCpmModelCacheRoot);
                File.AppendAllText(
                    bootstrapLogPath,
                    "VoxCPM setup started: " + DateTime.Now.ToString("s") + Environment.NewLine
                        + "Model download mirror: " + (useHfMirror ? "enabled" : "disabled") + Environment.NewLine,
                    Encoding.UTF8);
                Directory.CreateDirectory(tempDir);
                using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("voxcpm_service.zip"))
                {
                    if (stream == null)
                    {
                        throw new InvalidOperationException("VoxCPM setup resource missing.");
                    }

                    using (var output = File.Create(tempZip))
                    {
                        stream.CopyTo(output);
                    }
                }

                ExtractZipToDirectory(tempZip, tempDir);
                var scriptPath = Path.Combine(tempDir, "install_local.ps1");
                if (!File.Exists(scriptPath))
                {
                    throw new FileNotFoundException("VoxCPM setup script missing.", scriptPath);
                }

                var startInfo = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"" + scriptPath + "\""
                        + " -InstallRoot " + QuoteProcessArgument(voxCpmInstallRoot)
                        + " -ModelCacheRoot " + QuoteProcessArgument(voxCpmModelCacheRoot)
                        + (useHfMirror ? " -UseHfMirror" : ""),
                    WorkingDirectory = tempDir,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                using (var setupLog = new StreamWriter(bootstrapLogPath, true, Encoding.UTF8))
                using (var process = new Process())
                {
                    setupLog.AutoFlush = true;
                    setupLog.WriteLine("Command: powershell.exe " + startInfo.Arguments);
                    process.StartInfo = startInfo;
                    process.OutputDataReceived += delegate(object outputSender, DataReceivedEventArgs outputArgs)
                    {
                        if (outputArgs.Data != null)
                        {
                            setupLog.WriteLine(outputArgs.Data);
                        }
                    };
                    process.ErrorDataReceived += delegate(object errorSender, DataReceivedEventArgs errorArgs)
                    {
                        if (errorArgs.Data != null)
                        {
                            setupLog.WriteLine(errorArgs.Data);
                        }
                    };
                    if (!process.Start())
                    {
                        throw new InvalidOperationException("Could not start PowerShell for VoxCPM setup.");
                    }
                    process.BeginOutputReadLine();
                    process.BeginErrorReadLine();
                    process.WaitForExit();
                    if (process.ExitCode != 0)
                    {
                        MessageBox.Show(
                            this,
                            "VoxCPM setup failed. The main app installation completed.\n\nSetup log: " + logPath + "\nBootstrap log: " + bootstrapLogPath,
                            "Oh My Word",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Warning);
                        return;
                    }
                }

                MessageBox.Show(
                    this,
                    "VoxCPM local setup completed.",
                    "Oh My Word",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    this,
                    "VoxCPM setup failed. The main app installation completed.\n\nSetup log: " + logPath + "\nBootstrap log: " + bootstrapLogPath + "\n\n" + ex.Message,
                    "Oh My Word",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
            }
            finally
            {
                try
                {
                    if (Directory.Exists(tempDir))
                    {
                        Directory.Delete(tempDir, true);
                    }
                }
                catch
                {
                }
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

    private static string NormalizeVoxCpmInstallRoot(string rawPath)
    {
        return NormalizeInstallRoot(rawPath);
    }

    private static string NormalizeVoxCpmModelCacheRoot(string rawPath)
    {
        return NormalizeInstallRoot(rawPath);
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

    private static void EnsureVoxCpmSetupDirectories(string voxCpmInstallRoot, string voxCpmModelCacheRoot)
    {
        ProbeWritableDirectory(voxCpmInstallRoot, "VoxCPM engine folder");
        ProbeWritableDirectory(voxCpmModelCacheRoot, "VoxCPM model cache folder");
        ProbeWritableDirectory(Path.Combine(voxCpmModelCacheRoot, "hub"), "VoxCPM model cache folder");
    }

    private static void ProbeWritableDirectory(string directoryPath, string description)
    {
        try
        {
            Directory.CreateDirectory(directoryPath);
            var probePath = Path.Combine(directoryPath, ".oh-my-word-write-test-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                File.WriteAllText(probePath, "ok");
            }
            finally
            {
                if (File.Exists(probePath))
                {
                    File.Delete(probePath);
                }
            }
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                "Cannot write to " + description + ": " + directoryPath
                + Environment.NewLine
                + "Choose a writable location and try again.",
                ex);
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

    private static string QuoteProcessArgument(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
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
    "/resource:$voxcpmServiceZipPath,voxcpm_service.zip",
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
