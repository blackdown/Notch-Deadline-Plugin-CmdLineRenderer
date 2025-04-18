from Deadline.Plugins import *
from Deadline.Scripting import RepositoryUtils
import os

def GetDeadlinePlugin():
    return NotchCmdRenderPlugin()

class NotchCmdRenderPlugin(DeadlinePlugin):
    def __init__(self):
        super().__init__()
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument

    def LogInfoWithProgress(self, message):
        """Log info message and update progress"""
        self.LogInfo(message)
        self.SetStatusMessage(message)

    def LogErrorWithGUI(self, message):
        """Log error to both GUI and Deadline logging system"""
        # Remove any System.Windows.Forms references
        self.LogError(message)
        self.SetStatusMessage(f"Error: {message}")

    def LogWarningWithGUI(self, message):
        """Log warning to both GUI and Deadline logging system"""
        # Remove any System.Windows.Forms references
        self.LogWarning(message)
        self.SetStatusMessage(f"Warning: {message}")

    def FailRender(self, message):
        """Override to provide more detailed error messages"""
        self.LogErrorWithGUI(message)
        super(NotchCmdRenderPlugin, self).FailRender(message)

    def InitializeProcess(self):
        # Automatically set SingleFramesOnly if IndividualFrames is checked
        individual_frames = self.GetBooleanPluginInfoEntryWithDefault("IndividualFrames", False)
        self.SingleFramesOnly = individual_frames
        self.LogInfoWithProgress(f"Set SingleFramesOnly to: {self.SingleFramesOnly}")

        self.PluginType = PluginType.Simple
        self.StdoutHandling = True

        # Validate executable
        exec_path = self.GetRenderExecutableCandidate()
        if not os.path.exists(exec_path):
            self.FailRender(
                f"Unable to find Notch Command Line Renderer.\n\n"
                f"Expected location: {exec_path}\n\n"
                "Please ensure Notch is installed correctly and the executable path "
                "is set properly in NotchCmdRender.param"
            )
        self.LogInfoWithProgress(f"Using Render Executable: {exec_path}")

    def GetRenderExecutableCandidate(self):
        program_files = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or "C:\\Program Files"
        self.hardcoded_exec_path = os.path.join(program_files, "Notch 1.0", "NotchCmdLineRender.exe")

        param_path = RepositoryUtils.GetRepositoryFilePath("custom/plugins/NotchCmdRender/NotchCmdRender.param", True)
        self.param_exec_path = None
        try:
            with open(param_path, "r") as f:
                for line in f:
                    if line.strip().startswith("RenderExecutable="):
                        _, val = line.split("=", 1)
                        self.param_exec_path = val.strip()
                        break
        except Exception as e:
            self.LogWarningWithGUI(
                f"Could not read NotchCmdRender.param:\n{str(e)}\n\n"
                "Will attempt to use default executable location"
            )

        if self.param_exec_path and os.path.exists(self.param_exec_path):
            return self.param_exec_path
        return self.hardcoded_exec_path

    def RenderExecutable(self):
        try:
            exec_path = self.GetRenderExecutableCandidate()
            return exec_path
        except Exception as e:
            self.FailRender(
                "Failed to get render executable:\n\n"
                f"Error: {str(e)}\n\n"
                "Please check the plugin configuration and Notch installation"
            )

    def RenderArgument(self):
        try:
            self.LogInfoWithProgress("RenderArgument: started")

            # Use job frame or override with current frame for IndividualFrames
            frame = self.GetStartFrame()
            individual_frames = self.GetBooleanPluginInfoEntryWithDefault("IndividualFrames", False)

            if individual_frames:
                start = end = frame
                self.LogInfoWithProgress(f"Individual frame mode: rendering only frame {frame}")
            else:
                start = self.GetIntegerPluginInfoEntryWithDefault("StartFrame", frame)
                end = self.GetIntegerPluginInfoEntryWithDefault("EndFrame", frame)
                self.LogInfoWithProgress(f"Rendering full frame range: {start} to {end}")

            args = []

            def quote(val):
                return f'"{val}"' if val and not val.startswith('"') else val

            def opt(key, flag, cast=str):
                value = self.GetPluginInfoEntryWithDefault(key, "")
                self.LogInfoWithProgress(f"{key} = '{value}'")
                if value != "":
                    try:
                        args.extend([flag, quote(str(cast(value)))])
                        self.LogInfoWithProgress(f"Added: {flag} {value}")
                    except Exception as e:
                        self.LogWarningWithGUI(
                            f"Skipped parameter {key}:\n"
                            f"Value: {value}\n"
                            f"Error: {str(e)}"
                        )

            scene = self.GetPluginInfoEntryWithDefault("SceneFile", "")
            output = self.GetPluginInfoEntryWithDefault("OutputPath", "")

            if not scene:
                self.FailRender(
                    "No scene file specified.\n\n"
                    "Please select a valid Notch (.dfx) file"
                )
            if not output:
                self.FailRender(
                    "No output path specified.\n\n"
                    "Please specify an output file path"
                )

            # Append frame number to filename for individual frames
            if individual_frames:
                base, ext = os.path.splitext(output)
                output = f"{base}_{frame:04d}{ext}"

            # Add required parameters first
            args.extend([
                "-document", quote(scene),
                "-out", quote(output),
                "-startFrame", str(start),
                "-endFrame", str(end)
            ])

            # Optional params with validation
            try:
                opt("Codec", "-Codec", str)
            except Exception as e:
                self.FailRender(f"Invalid codec parameter:\n{str(e)}")

            try:
                opt("ResX", "-Width", int)
                opt("ResY", "-Height", int)
            except Exception as e:
                self.FailRender(
                    f"Invalid resolution parameters:\n\n"
                    f"Error: {str(e)}\n\n"
                    "Width and Height must be valid numbers"
                )

            # Remaining optional params
            opt("FPS", "-fps", float)
            opt("Quality", "-quality", int)
            opt("BitRate", "-bitrate", int)
            opt("LogFile", "-logfile", str)
            opt("Refines", "-refines", int)
            opt("Layer", "-layer", int)

            extra = self.GetPluginInfoEntryWithDefault("ExtraArgs", "").strip()
            if extra:
                args.extend(extra.split())
                self.LogInfoWithProgress(f"ExtraArgs: {extra}")

            final_args = " ".join(args)
            self.LogInfoWithProgress("Final Render Command:")
            self.LogInfoWithProgress(final_args)
            return final_args
            
        except Exception as e:
            self.FailRender(
                "Failed to build render command:\n\n"
                f"Error: {str(e)}\n\n"
                "Please check all parameters and try again"
            )

def CleanupDeadlinePlugin(plugin):
    """Clean up any resources used by the plugin"""
    plugin.LogInfoWithProgress("NotchCmdRender cleanup complete.")
