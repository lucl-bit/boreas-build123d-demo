namespace BoreasVoxel;

/// <summary>Einstieg: dotnet run --project voxel -c Release -- --spec ... --task ... --out ... (siehe PLAN.md).</summary>
public static class Program
{
    public static int Main(string[] args) => Cli.Run(args);
}
