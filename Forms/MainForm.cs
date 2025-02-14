using DawnBreaker.Common;
using System.Globalization;
using System.Management;
namespace DawnBreaker
{
    public partial class MainForm : Form
    {
        public class DataCombo
        {
            public string Name { get; set; } = string.Empty;
            public string Command { get; set; } = string.Empty;
        }

        public List<DataCombo> stringCombos = new List<DataCombo>
        {
            new DataCombo{ Name = "检验邮箱", Command = "email"},
            new DataCombo{ Name = "检验IP地址", Command = "ip"},
            new DataCombo{ Name = "检验MAC地址", Command = "mac"},
            new DataCombo{ Name = "检验URL地址", Command = "url"},
            new DataCombo{ Name = "检验身份证号码", Command = "idcard"},
            new DataCombo{ Name = "AES加密", Command = "aesenc"},
            new DataCombo{ Name = "AES解密", Command = "aesdec"},
            new DataCombo{ Name = "DES加密", Command = "desenc"},
            new DataCombo{ Name = "DES解密", Command = "desdec"}
        };

        public List<DataCombo> systeminfoCombos = new List<DataCombo>
        {
            new DataCombo{ Name = "基本信息", Command = "base"},
            new DataCombo{ Name = "计算机系统", Command = "cs"},
            new DataCombo{ Name = "主板", Command = "bb"},
            new DataCombo{ Name = "中央处理器", Command = "cpu"},
            new DataCombo{ Name = "显示适配器", Command = "gpu"},
            new DataCombo{ Name = "显示器", Command = "dm"},
            new DataCombo{ Name = "磁盘驱动器", Command = "dd"},
            new DataCombo{ Name = "逻辑磁盘（分区）", Command = "ld"},
            new DataCombo{ Name = "物理内存", Command = "pm"},
            new DataCombo{ Name = "音频适配器", Command = "sd"},
            new DataCombo{ Name = "网络适配器", Command = "na"},
            new DataCombo{ Name = "网络适配器配置", Command = "nac"},
            new DataCombo{ Name = "操作系统", Command = "os"},
            new DataCombo{ Name = "BIOS", Command = "bios"},
            new DataCombo{ Name = "进程状态", Command = "process"},
            new DataCombo{ Name = "服务状态", Command = "service"},
            new DataCombo{ Name = "软件", Command = "product"},
            new DataCombo{ Name = "启动配置", Command = "bootcfg"},
            new DataCombo{ Name = "开机启动项", Command = "sc"},
            new DataCombo{ Name = "系统环境变量", Command = "env"},
            new DataCombo{ Name = "用户账户信息", Command = "ua"}
        };

        public MainForm()
        {
            InitializeComponent();
            InitializeUI();
        }

        private void InitializeUI()
        {
            StringComboBox.DataSource = stringCombos;
            StringComboBox.DisplayMember = "Name";
            StringComboBox.ValueMember = "Command";
            StringComboBox.SelectedIndex = 0;
            SystemInfoComboBox.DataSource = systeminfoCombos;
            SystemInfoComboBox.DisplayMember = "Name";
            SystemInfoComboBox.ValueMember = "Command";
            SystemInfoComboBox.SelectedIndex = 0;
        }

        private void StringButton_Click(object sender, EventArgs e)
        {
            if (InputTextBox.Text == "")
            {
                OutputTextBox.Text = "INPUT NULL";
                return;
            }
            OutputTextBox.Text = "";
            foreach (string input in InputTextBox.Lines)
            {
                string output;
                string tradetime = DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss (zz)", DateTimeFormatInfo.InvariantInfo);
                TimeSpan timeSpan = DateTime.Now - new DateTime(1970, 1, 1); ;
                string ret = Convert.ToInt64(timeSpan.TotalMilliseconds).ToString();
                switch (StringComboBox.SelectedValue)
                {
                    case "email":
                        output = input.MatchEmail().ToString();
                        OutputTextBox.Text += output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"match -t email -s {InputTextBox.Text}");
                        Console.WriteLine(output);
                        break;
                    case "ip":
                        string iptype;
                        output = input.MatchIP(out iptype).ToString() + $" iptype:{iptype}";
                        OutputTextBox.Text += output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"match -t ip -s {InputTextBox.Text}");
                        Console.WriteLine(output);
                        break;
                    case "mac":
                        output = input.MatchMac().ToString();
                        OutputTextBox.Text += output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"match -t mac -s {InputTextBox.Text}");
                        Console.WriteLine(output);
                        break;
                    case "url":
                        output = input.MatchURL().ToString();
                        OutputTextBox.Text += output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"match -t url -s {InputTextBox.Text}");
                        Console.WriteLine(output);
                        break;
                    case "idcard":
                        string[] cardinfo = { };
                        if (input.MatchIdentifyCard(out cardinfo))
                        {
                            output = input.MatchIdentifyCard(out cardinfo).ToString() + $" {cardinfo[0]} {cardinfo[1]} {cardinfo[2]}";
                        }
                        else
                        {
                            output = input.MatchIdentifyCard(out cardinfo).ToString();
                        }
                        OutputTextBox.Text += output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"match -t idcard -s {InputTextBox.Text}");
                        Console.WriteLine(output);
                        break;
                    case "aesenc":
                        output = InputTextBox.Lines[0].AESEncrypt(InputTextBox.Lines[1]);
                        OutputTextBox.Text = output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"enc -t aes -s {InputTextBox.Lines[0]} -k {InputTextBox.Lines[1]}");
                        Console.WriteLine(output);
                        break;
                    case "aesdec":
                        output = InputTextBox.Lines[0].AESDecrypt(InputTextBox.Lines[1]);
                        OutputTextBox.Text = output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"dec -t aes -s {InputTextBox.Lines[0]} -k {InputTextBox.Lines[1]}");
                        Console.WriteLine(output);
                        break;
                    case "desenc":
                        output = InputTextBox.Lines[0].DESEncrypt(InputTextBox.Lines[1]);
                        OutputTextBox.Text = output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"enc -t des -s {InputTextBox.Lines[0]} -k {InputTextBox.Lines[1]}");
                        Console.WriteLine(output);
                        break;
                    case "desdec":
                        output = InputTextBox.Lines[0].DESDecrypt(InputTextBox.Lines[1]);
                        OutputTextBox.Text = output;
                        Console.WriteLine(tradetime + " " + ret);
                        Console.WriteLine($"dec -t des -s {InputTextBox.Lines[0]} -k {InputTextBox.Lines[1]}");
                        Console.WriteLine(output);
                        break;
                }
                OutputTextBox.Text += "\r\n";
            }

        }

        private void SystemInfoComboBox_SelectedIndexChanged(object sender, EventArgs e)
        {
            string query;
            string output = "";
            string tradetime = DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss (zz)", DateTimeFormatInfo.InvariantInfo);
            TimeSpan timeSpan = DateTime.Now - new DateTime(1970, 1, 1); ;
            string ret = Convert.ToInt64(timeSpan.TotalMilliseconds).ToString();
            switch (SystemInfoComboBox.SelectedValue)
            {
                case "base":
                    string[] basecommands =
                    [
                        "SELECT * FROM Win32_BaseBoard",
                        "SELECT * FROM Win32_Processor",
                        "SELECT * FROM Win32_VideoController",
                        "SELECT * FROM Win32_DiskDrive",
                        "SELECT * FROM Win32_PhysicalMemory",
                        "SELECT * FROM Win32_NetworkAdapter",
                        "SELECT * FROM Win32_SoundDevice",
                        "SELECT * FROM Win32_DesktopMonitor",
                        "SELECT * FROM Win32_OperatingSystem"
                    ];
                    for (int i = 0; i < basecommands.Length; i++)
                    {
                        int index = 0;
                        ManagementObjectSearcher searchers = new ManagementObjectSearcher(basecommands[i]);
                        switch (i)
                        {
                            case 0:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"主板\t型号: {obj["Product"] ?? "未知"}\r\n");
                                }
                                break;
                            case 1:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"CPU\t核心数: {obj["NumberOfCores"] ?? "未知"}\r\n" +
                                        $"\t型号: {obj["Name"]?.ToString().Trim() ?? "未知"}\r\n" +
                                        $"\t逻辑处理器: {obj["NumberOfLogicalProcessors"] ?? "未知"}\r\n" +
                                        $"\t主频: {(obj["MaxClockSpeed"] != null ? $"{Convert.ToDouble(obj["MaxClockSpeed"]) / 1000} GHz" : "未知")}\r\n" +
                                        $"\t缓存: L2 {obj["L2CacheSize"] ?? "未知"}KB | L3 {obj["L3CacheSize"] ?? "未知"}KB\r\n");
                                }
                                break;
                            case 2:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"GPU{++index}\t型号: {obj["Name"] ?? "未知"}\r\n" +
                                        $"\t显存: {(obj["AdapterRAM"] != null ? $"{Convert.ToUInt64(obj["AdapterRAM"]) / (1024 * 1024 * 1024)} GB" : "未知")}\r\n" +
                                        $"\t位宽: {obj["CurrentBitsPerPixel"] ?? "未知"} bit\r\n");
                                }
                                break;
                            case 3:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"存储{++index}\t型号: {obj["Model"]?.ToString().Trim() ?? "未知"}\r\n" +
                                        $"\t容量: {(obj["Size"] != null ? $"{Convert.ToUInt64(obj["Size"]) / (1024 * 1024 * 1024)} GB" : "未知")}\r\n" +
                                        $"\t接口: {obj["InterfaceType"] ?? "未知"}\r\n");
                                }
                                break;
                            case 4:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"内存{++index}\t型号: {obj["PartNumber"]?.ToString().Trim() ?? "未知"}\r\n" +
                                        $"\t容量: {(obj["Capacity"] != null ? $"{Convert.ToUInt64(obj["Capacity"]) / (1024 * 1024 * 1024)} GB" : "未知")}\r\n" +
                                        $"\t频率: {obj["Speed"] ?? "未知"} MHz\r\n");
                                }
                                break;
                            case 5:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"网络适配器{++index}\t型号: {obj["ProductName"] ?? "未知"}\r\n");
                                }
                                break;
                            case 6:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"音频适配器{++index}\t型号: {obj["ProductName"] ?? "未知"}\r\n");
                                }
                                break;
                            case 7:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"显示器{++index}\t型号: {obj["Name"] ?? "未知"}\r\n");
                                }
                                break;
                            case 8:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"操作系统\t名称: {obj["Caption"] ?? "未知"}\r\n" +
                                        $"\t版本: {obj["Version"] ?? "未知"}\r\n");
                                }
                                break;
                        }
                    }
                    SystemInfoTextBox.Text = output;
                    Console.WriteLine(tradetime + " " + ret);
                    Console.WriteLine("sys -t base");
                    Console.WriteLine(output);
                    return;
                case "cs":
                    query = "SELECT * FROM Win32_ComputerSystem";
                    break;
                case "bb":
                    query = "SELECT * FROM Win32_BaseBoard";
                    break;
                case "cpu":
                    query = "SELECT * FROM Win32_Processor";
                    break;
                case "gpu":
                    query = "SELECT * FROM Win32_VideoController";
                    break;
                case "dm":
                    query = "SELECT * FROM Win32_DesktopMonitor";
                    break;
                case "dd":
                    query = "SELECT * FROM Win32_DiskDrive";
                    break;
                case "ld":
                    query = "SELECT * FROM Win32_LogicalDisk";
                    break;
                case "pm":
                    query = "SELECT * FROM Win32_PhysicalMemory";
                    break;
                case "sd":
                    query = "SELECT * FROM Win32_SoundDevice";
                    break;
                case "na":
                    query = "SELECT * FROM Win32_NetworkAdapter";
                    break;
                case "nac":
                    query = "SELECT * FROM Win32_NetworkAdapterConfiguration";
                    break;
                case "os":
                    query = "SELECT * FROM Win32_OperatingSystem";
                    break;
                case "bios":
                    query = "SELECT * FROM Win32_BIOS";
                    break;
                case "process":
                    query = "SELECT * FROM Win32_Process";
                    break;
                case "service":
                    query = "SELECT * FROM Win32_Service";
                    break;
                case "product":
                    query = "SELECT * FROM Win32_Product";
                    break;
                case "bootcfg":
                    query = "SELECT * FROM Win32_BootConfiguration";
                    break;
                case "sc":
                    query = "SELECT * FROM Win32_StartupCommand";
                    break;
                case "env":
                    query = "SELECT * FROM Win32_Environment";
                    break;
                case "ua":
                    query = "SELECT * FROM Win32_UserAccount";
                    break;
                default:
                    return;
            }
            ManagementObjectSearcher searcher = new ManagementObjectSearcher(query);
            try
            {
                foreach (ManagementObject obj in searcher.Get())
                {
                    foreach (PropertyData property in obj.Properties)
                    {
                        object value = property.Value;
                        string displayValue;

                        if (value == null)
                        {
                            displayValue = "null";
                        }
                        else if (value is Array array)
                        {
                            displayValue = string.Join(", ", array.Cast<object>());
                        }
                        else
                        {
                            displayValue = value.ToString();
                        }
                        if (property.Name == "OEMLogoBitmap") continue;
                        output += ($"{property.Name}: {displayValue}\r\n");
                    }
                }
            }
            catch
            {
                output += ("查询失败");
            }
            SystemInfoTextBox.Text = output;
            Console.WriteLine(tradetime + " " + ret);
            Console.WriteLine($"sys -t {SystemInfoComboBox.SelectedValue}");
            Console.WriteLine(output);
        }

        private void AboutButton_Click(object sender, EventArgs e)
        {
            MessageBox.Show("DawnBreaker 破晓工具 V1.0.0.0 20250215\n" +
                "Copyright 2025 All Rights Reserved. 哀歌殇年 版权所有\n" +
                "官网: https://agsn.site/\n" +
                "作者QQ: 2690034441", "关于");
        }
    }
}
