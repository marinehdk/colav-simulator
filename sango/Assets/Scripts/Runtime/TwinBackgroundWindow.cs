using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace Sango
{
    /// <summary>Keep the normal Metal render loop while the WEB-only player has no visible UI.</summary>
    [DefaultExecutionOrder(-10000)]
    public sealed class TwinBackgroundWindow : MonoBehaviour
    {
#if UNITY_STANDALONE_OSX && !UNITY_EDITOR
        const string ObjC = "/usr/lib/libobjc.A.dylib";
        [DllImport(ObjC)] static extern IntPtr objc_getClass(string name);
        [DllImport(ObjC)] static extern IntPtr sel_registerName(string name);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern IntPtr Pointer(IntPtr obj, IntPtr sel);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern IntPtr PointerAt(IntPtr obj, IntPtr sel, long index);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern long Count(IntPtr obj, IntPtr sel);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern byte Boolean(IntPtr obj, IntPtr sel);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern byte SetPolicy(IntPtr obj, IntPtr sel, long policy);
        [DllImport(ObjC, EntryPoint = "objc_msgSend")] static extern void Action(IntPtr obj, IntPtr sel, IntPtr sender);
        static IntPtr s_App;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSplashScreen)]
        static void BeforeSplash()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "--sango-web-only") < 0) return;
            s_App = Pointer(objc_getClass("NSApplication"), sel_registerName("sharedApplication"));
            SetPolicy(s_App, sel_registerName("setActivationPolicy:"), 2); // prohibited: no Dock/menu/key window
            HideOwnWindows();
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AfterScene()
        {
            if (s_App == IntPtr.Zero) return;
            var host = new GameObject("Twin WEB-only window host");
            DontDestroyOnLoad(host);
            host.AddComponent<TwinBackgroundWindow>();
            Debug.Log("[Sango.TwinVideo] WEB-only normal Metal renderer; application windows hidden");
        }

        static long HideOwnWindows()
        {
            if (s_App == IntPtr.Zero) return 0;
            Action(s_App, sel_registerName("hide:"), IntPtr.Zero);
            var windows = Pointer(s_App, sel_registerName("windows"));
            long count = Count(windows, sel_registerName("count"));
            for (long i = 0; i < count; i++)
                Action(PointerAt(windows, sel_registerName("objectAtIndex:"), i), sel_registerName("orderOut:"), IntPtr.Zero);
            long visible = 0;
            for (long i = 0; i < count; i++)
                if (Boolean(PointerAt(windows, sel_registerName("objectAtIndex:"), i), sel_registerName("isVisible")) != 0) visible++;
            return visible;
        }

        float m_NextAudit;
        void Update()
        {
            long visible = HideOwnWindows();
            if (Time.realtimeSinceStartup >= m_NextAudit)
            {
                Debug.Log($"[Sango.TwinVideo] visible_windows={visible}");
                m_NextAudit = Time.realtimeSinceStartup + 10f;
            }
        }
#endif
    }
}
