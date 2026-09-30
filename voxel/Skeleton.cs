using System.Numerics;

namespace BoreasVoxel;

/// <summary>Skelett (Master): nur die Schnittstellenmasse, die mehrere Gruppen gemeinsam nutzen.
/// Jede Feature-Gruppe bekommt genau dieses Objekt plus ihre eigene GroupView, sonst nichts (Skelett-Methode, PLAN.md).</summary>
public sealed class Skeleton
{
    public int ArmCount; public float ArmAngleOffset, ArmSplay, MotorRadius, SplitZ, JointRadius, NoseJointZ, NoseJointRadius, BodyBottomZ;

    public static Skeleton From(Spec spec)
    {
        var g = spec.View("skeleton");
        return new Skeleton
        {
            ArmCount = g.I("arm_count"), ArmAngleOffset = g.F("arm_angle_offset"), ArmSplay = g.F("arm_splay"), MotorRadius = g.F("motor_radius"),
            SplitZ = g.F("split_z"), JointRadius = g.F("joint_radius"), NoseJointZ = g.F("nose_joint_z"), NoseJointRadius = g.F("nose_joint_radius"),
            BodyBottomZ = g.F("body_bottom_z")
        };
    }

    /// <summary>Winkel (Grad, von +X gegen den Uhrzeigersinn) des Arms i: offset + i*360/n + (-1)^i * splay.</summary>
    public float ArmAngle(int i) => ArmAngleOffset + i * 360f / ArmCount + ((i & 1) == 0 ? 1 : -1) * ArmSplay;

    /// <summary>Winkel der Zwischenraeume (Mittelwinkel zwischen zwei Nachbararmen).</summary>
    public float GapAngle(int i) { float a = ArmAngle(i), b = ArmAngle(i + 1) + (i + 1 == ArmCount ? 360f : 0f); return (a + b) / 2f; }

    /// <summary>Radialrichtung in der XY-Ebene.</summary>
    public static Vector3 Dir(float deg) => new(MathF.Cos(deg * Geo.Deg), MathF.Sin(deg * Geo.Deg), 0);

    public Vector3 MotorPos(int i) => Dir(ArmAngle(i)) * MotorRadius + new Vector3(0, 0, SplitZ);

    public string Fingerprint() => string.Join(";", ArmCount, ArmAngleOffset, ArmSplay, MotorRadius, SplitZ, JointRadius, NoseJointZ, NoseJointRadius, BodyBottomZ);
}
