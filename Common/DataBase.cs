using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace DawnBreaker.Common
{
    internal class DataBase
    {
        public static readonly List<Command> Commands = new List<Command>()
        {
            new Command("help","获取帮助",new List<List<string>>(){
                new List<string>(){ "-c", "value", "获取指定指令的具体帮助" },
            }),
            new Command("about","相关信息",new List<List<string>>(){
                new List<string>(){ "--v", "flag", "获取版本信息" },
            }),
            new Command("match","检验字符串",new List<List<string>>(){
                new List<string>(){ "-s", "value", "必须的。待检验字符串" },
                new List<string>(){ "-t", "value", "必须的。待检验格式类型\n" +
                    "合法的参数：\n" +
                    "email\t邮箱\n" +
                    "ip\tIP地址\n" +
                    "mac\tMAC地址\n" +
                    "url\tURL地址\n" +
                    "idcard\t身份证号码（中国大陆）\n" +
                    "未来会支持的参数（正在实现）：手机号码（中国大陆）" }
            }),
            new Command("enc","加密字符串",new List<List<string>>(){
                new List<string>(){ "-s", "value", "必须的。待加密字符串" },
                new List<string>(){ "-k", "value", "必须的。加密密钥" },
                new List<string>(){ "-t", "value", "必须的。加密算法\n" +
                    "合法的参数：\n" +
                    "aes\tAES\n" +
                    "des\tDES\n" +
                    "未来会支持的参数（正在实现）：RC2、RSA、ECC、MD5、SHA-1、SHA-255" }
            }),
            new Command("dec","解密字符串",new List<List<string>>(){
                new List<string>(){ "-s", "value", "必须的。待解密字符串" },
                new List<string>(){ "-k", "value", "必须的。解密密钥" },
                new List<string>(){ "-t", "value", "必须的。加密算法\n" +
                    "合法的参数：\n" +
                    "aes\tAES\n" +
                    "des\tDES\n" +
                    "未来会支持的参数（正在实现）：RC2、RSA、ECC、MD5、SHA-1、SHA-255" }
            }),
            new Command("sys","查询计算机信息",new List<List<string>>(){
                new List<string>(){ "-w", "value", "必须的。待查询内容\n" +
                    "合法的参数：\n" +
                    "cs\t计算机系统\n" +
                    "bb\t主板\n" +
                    "cpu\t中央处理器\n" +
                    "gpu\t显示适配器\n" +
                    "dm\t显示器\n" +
                    "dd\t磁盘驱动器\n" +
                    "ld\t逻辑磁盘（分区）\n" +
                    "pm\t物理内存\n" +
                    "sd\t音频适配器\n" +
                    "na\t网络适配器\n" +
                    "nac\t网络适配器配置\n" +
                    "os\t操作系统\n" +
                    "bios\t BIOS\n" +
                    "process\t现行进程\n" +
                    "service\t服务状态\n" +
                    "product\t现装软件\n" +
                    "bootcfg\t启动配置\n" +
                    "sc\t开机启动项\n" +
                    "env\t系统环境变量\n" +
                    "ua\t用户账户信息\n" },
                new List<string>(){ "--v", "flag", "输出详细信息" }
            })
        };

        public class Command
        {
            public string Name { get; set; }
            public string Description { get; set; }
            public List<List<string>> Options { get; set; }
            public Command(string name, string description, List<List<string>> options)
            {
                Name = name;
                Description = description;
                Options = options ?? new List<List<string>>();
            }
        }


        public static readonly Dictionary<string, string> ProvinceCodes = new Dictionary<string, string>
        {
        {"11","北京市"}, {"12","天津市"}, {"13","河北省"}, {"14","山西省"},
        {"15","内蒙古自治区"}, {"21","辽宁省"}, {"22","吉林省"}, {"23","黑龙江省"},
        {"31","上海市"}, {"32","江苏省"}, {"33","浙江省"}, {"34","安徽省"},
        {"35","福建省"}, {"36","江西省"}, {"37","山东省"}, {"41","河南省"},
        {"42","湖北省"}, {"43","湖南省"}, {"44","广东省"}, {"45","广西壮族自治区"},
        {"46","海南省"}, {"50","重庆市"}, {"51","四川省"}, {"52","贵州省"},
        {"53","云南省"}, {"54","西藏自治区"}, {"61","陕西省"}, {"62","甘肃省"},
        {"63","青海省"}, {"64","宁夏回族自治区"}, {"65","新疆维吾尔自治区"},
        {"71","台湾省"}, {"81","香港特别行政区"}, {"82","澳门特别行政区"}
        };
    }
}
