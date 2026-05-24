using System;
using System.IO;
using Windows.Media.SpeechSynthesis;
using Windows.Storage.Streams;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: OneCoreTTS.exe <voice> <output.wav|-|--play> [text|-]");
    return 1;
}

string voiceName = args[0];
string outputArg = args[1];
bool playOnly = outputArg == "--play" || outputArg == "-play";

string text;
if (args.Length > 2 && args[2] != "-")
    text = args[2];
else
    text = Console.In.ReadToEnd();

try
{
    var synth = new SpeechSynthesizer();

    foreach (var v in SpeechSynthesizer.AllVoices)
    {
        if (v.DisplayName.Equals(voiceName, StringComparison.OrdinalIgnoreCase) ||
            v.DisplayName.StartsWith(voiceName, StringComparison.OrdinalIgnoreCase))
        {
            synth.Voice = v;
            break;
        }
    }

    var stream = await synth.SynthesizeTextToStreamAsync(text);
    var dataReader = new DataReader(stream);
    await dataReader.LoadAsync((uint)stream.Size);
    byte[] buffer = new byte[stream.Size];
    dataReader.ReadBytes(buffer);

    if (playOnly)
    {
        string tmpWav = Path.Combine(Path.GetTempPath(), $"tts_{Guid.NewGuid():N}.wav");
        File.WriteAllBytes(tmpWav, buffer);
        // Use Windows native play (sndPlaySound via winmm)
        NativeMethods.PlaySound(tmpWav, IntPtr.Zero, 0x00020000); // SND_FILENAME | SND_SYNC
        try { File.Delete(tmpWav); } catch { }
    }
    else
    {
        File.WriteAllBytes(outputArg, buffer);
    }

    Console.WriteLine($"OK|{synth.Voice.DisplayName}|{synth.Voice.Language}|{buffer.Length}");
    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"ERR|{ex.Message}");
    return 1;
}

static class NativeMethods
{
    [System.Runtime.InteropServices.DllImport("winmm.dll", SetLastError = true)]
    public static extern bool PlaySound(string pszSound, IntPtr hmod, uint fdwSound);
}
