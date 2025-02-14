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
            new DataCombo{ Name = "��������", Command = "email"},
            new DataCombo{ Name = "����IP��ַ", Command = "ip"},
            new DataCombo{ Name = "����MAC��ַ", Command = "mac"},
            new DataCombo{ Name = "����URL��ַ", Command = "url"},
            new DataCombo{ Name = "�������֤����", Command = "idcard"},
            new DataCombo{ Name = "AES����", Command = "aesenc"},
            new DataCombo{ Name = "AES����", Command = "aesdec"},
            new DataCombo{ Name = "DES����", Command = "desenc"},
            new DataCombo{ Name = "DES����", Command = "desdec"}
        };

        public List<DataCombo> systeminfoCombos = new List<DataCombo>
        {
            new DataCombo{ Name = "������Ϣ", Command = "base"},
            new DataCombo{ Name = "�����ϵͳ", Command = "cs"},
            new DataCombo{ Name = "����", Command = "bb"},
            new DataCombo{ Name = "���봦����", Command = "cpu"},
            new DataCombo{ Name = "��ʾ������", Command = "gpu"},
            new DataCombo{ Name = "��ʾ��", Command = "dm"},
            new DataCombo{ Name = "����������", Command = "dd"},
            new DataCombo{ Name = "�߼����̣�������", Command = "ld"},
            new DataCombo{ Name = "�����ڴ�", Command = "pm"},
            new DataCombo{ Name = "��Ƶ������", Command = "sd"},
            new DataCombo{ Name = "����������", Command = "na"},
            new DataCombo{ Name = "��������������", Command = "nac"},
            new DataCombo{ Name = "����ϵͳ", Command = "os"},
            new DataCombo{ Name = "BIOS", Command = "bios"},
            new DataCombo{ Name = "����״̬", Command = "process"},
            new DataCombo{ Name = "����״̬", Command = "service"},
            new DataCombo{ Name = "���", Command = "product"},
            new DataCombo{ Name = "��������", Command = "bootcfg"},
            new DataCombo{ Name = "����������", Command = "sc"},
            new DataCombo{ Name = "ϵͳ��������", Command = "env"},
            new DataCombo{ Name = "�û��˻���Ϣ", Command = "ua"}
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
                                    output += ($"����\t�ͺ�: {obj["Product"] ?? "δ֪"}\r\n");
                                }
                                break;
                            case 1:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"CPU\t������: {obj["NumberOfCores"] ?? "δ֪"}\r\n" +
                                        $"\t�ͺ�: {obj["Name"]?.ToString().Trim() ?? "δ֪"}\r\n" +
                                        $"\t�߼�������: {obj["NumberOfLogicalProcessors"] ?? "δ֪"}\r\n" +
                                        $"\t��Ƶ: {(obj["MaxClockSpeed"] != null ? $"{Convert.ToDouble(obj["MaxClockSpeed"]) / 1000} GHz" : "δ֪")}\r\n" +
                                        $"\t����: L2 {obj["L2CacheSize"] ?? "δ֪"}KB | L3 {obj["L3CacheSize"] ?? "δ֪"}KB\r\n");
                                }
                                break;
                            case 2:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"GPU{++index}\t�ͺ�: {obj["Name"] ?? "δ֪"}\r\n" +
                                        $"\t�Դ�: {(obj["AdapterRAM"] != null ? $"{Convert.ToUInt64(obj["AdapterRAM"]) / (1024 * 1024 * 1024)} GB" : "δ֪")}\r\n" +
                                        $"\tλ��: {obj["CurrentBitsPerPixel"] ?? "δ֪"} bit\r\n");
                                }
                                break;
                            case 3:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"�洢{++index}\t�ͺ�: {obj["Model"]?.ToString().Trim() ?? "δ֪"}\r\n" +
                                        $"\t����: {(obj["Size"] != null ? $"{Convert.ToUInt64(obj["Size"]) / (1024 * 1024 * 1024)} GB" : "δ֪")}\r\n" +
                                        $"\t�ӿ�: {obj["InterfaceType"] ?? "δ֪"}\r\n");
                                }
                                break;
                            case 4:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"�ڴ�{++index}\t�ͺ�: {obj["PartNumber"]?.ToString().Trim() ?? "δ֪"}\r\n" +
                                        $"\t����: {(obj["Capacity"] != null ? $"{Convert.ToUInt64(obj["Capacity"]) / (1024 * 1024 * 1024)} GB" : "δ֪")}\r\n" +
                                        $"\tƵ��: {obj["Speed"] ?? "δ֪"} MHz\r\n");
                                }
                                break;
                            case 5:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"����������{++index}\t�ͺ�: {obj["ProductName"] ?? "δ֪"}\r\n");
                                }
                                break;
                            case 6:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"��Ƶ������{++index}\t�ͺ�: {obj["ProductName"] ?? "δ֪"}\r\n");
                                }
                                break;
                            case 7:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += ($"��ʾ��{++index}\t�ͺ�: {obj["Name"] ?? "δ֪"}\r\n");
                                }
                                break;
                            case 8:
                                foreach (ManagementObject obj in searchers.Get())
                                {
                                    output += (
                                        $"����ϵͳ\t����: {obj["Caption"] ?? "δ֪"}\r\n" +
                                        $"\t�汾: {obj["Version"] ?? "δ֪"}\r\n");
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
                output += ("��ѯʧ��");
            }
            SystemInfoTextBox.Text = output;
            Console.WriteLine(tradetime + " " + ret);
            Console.WriteLine($"sys -t {SystemInfoComboBox.SelectedValue}");
            Console.WriteLine(output);
        }

        private void AboutButton_Click(object sender, EventArgs e)
        {
            MessageBox.Show("DawnBreaker �������� V1.0.0.0 20250215\n" +
                "Copyright 2025 All Rights Reserved. �������� ��Ȩ����\n" +
                "����: https://agsn.site/\n" +
                "����QQ: 2690034441", "����");
        }
    }
}
