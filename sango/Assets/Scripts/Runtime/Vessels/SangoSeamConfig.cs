using System;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子的编译期开关与常量（spec #86 Implementation Decisions）。
    /// PublisherEnabled = false：默认构建零开销（FramePublisher.OnEnable 早退，不建 socket、不协程）。
    /// 验收/探针启用路径见 PublisherCliFlag（运行期逃生口，不改变编译期默认），
    /// 全流程文档：sango/Docs/contracts/frame-publisher-v1.md。
    /// M9 增检测结果回传侧常量（端点/主题/旗标），协议文档：sango/Docs/contracts/detection-return-v1.md。
    /// </summary>
    public static class SangoSeamConfig
    {
        /// <summary>编译期总闸：false = 发布器在一切构建中默认关闭（spec 验收故事 5）。</summary>
        public const bool PublisherEnabled = false;

        /// <summary>FramePublisher PUB 绑定端点（localhost only；spec 建议值 tcp://127.0.0.1:5556）。</summary>
        public const string PublisherEndpoint = "tcp://127.0.0.1:5556";

        /// <summary>PUB 多帧消息第 1 帧：主题字符串（ZMQ PUB 订阅过滤用）。</summary>
        public const string PublisherTopic = "sango.frame";

        /// <summary>运行期启用逃生口：播放器命令行带此参数时 FramePublisher 强制启用（验收探针用，默认构建不带）。</summary>
        public const string PublisherCliFlag = "--sango-publisher";

        /// <summary>检测结果回传端点（detection-return-v1.md：服务端 PUB bind，Unity SUB connect）。</summary>
        public const string DetectionEndpoint = "tcp://127.0.0.1:5557";

        /// <summary>检测结果消息第 1 段：主题字符串（ZMQ PUB 订阅过滤用）。</summary>
        public const string DetectionTopic = "sango.detection";

        /// <summary>消费端 CLI 旗标：与 PublisherCliFlag 同值——seam 总闸一处开闸，发布/消费两侧同使能。</summary>
        public const string ConsumerCliFlag = PublisherCliFlag;

        /// <summary>
        /// P2-S1 Twin 数据面（spec #89）：Demo/Twin 模式开关的 Twin 启动旗标。
        /// 播放器命令行带此参数时 TwinSessionDriver 开闸（默认关闸，Demo 行为零变化）。
        /// </summary>
        public const string TwinCliFlag = "--sango-twin";

        /// <summary>Twin 数据面后端基址（gui_server 本机常驻，00-REPORT.md §2.2）。</summary>
        public const string TwinBackendBase = "http://127.0.0.1:8010";
    }
}
