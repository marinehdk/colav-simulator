using System;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子的编译期开关与常量（spec #86 Implementation Decisions）。
    /// PublisherEnabled = false：默认构建零开销（FramePublisher.OnEnable 早退，不建 socket、不协程）。
    /// 验收/探针启用路径见 PublisherCliFlag（运行期逃生口，不改变编译期默认），
    /// 全流程文档：sango/Docs/contracts/frame-publisher-v1.md。
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
    }
}
