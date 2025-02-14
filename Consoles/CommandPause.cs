using System;
using System.Collections.Generic;
using System.Diagnostics.Eventing.Reader;
using System.Linq;
using System.Management;
using System.Text;
using System.Threading.Tasks;
using DawnBreaker.Common;
namespace DawnBreaker.Consoles
{
    internal class CommandPause
    {
        public static void ProcessCommand(string[] args)
        {
            string commandName = args[0];
            DataBase.Command ?acommand = DataBase.Commands.FirstOrDefault(c => c.Name == commandName);
            if (DataBase.Commands.FirstOrDefault(c => c.Name == commandName) == null)
            {
                Console.WriteLine($"错误：未知命令 '{commandName}'。");
                return;
            }

            Dictionary<string, string> parameters = ParseParameters(args.Skip(1).ToArray(), acommand);
            if (parameters == null)
            {
                foreach (var command in DataBase.Commands)
                {
                    if (command.Name == commandName)
                    {
                        Console.WriteLine(command.Name + " " + command.Description);
                        foreach (var option in command.Options)
                        {
                            Console.WriteLine(option[0] + " " + option[2]);
                        }
                    }
                }
                return;
            }

            if (!ValidateParameters(acommand, parameters)) return;

            ExecuteCommand(commandName, parameters);
        }

        private static Dictionary<string, string> ParseParameters(string[] args, DataBase.Command command)
        {
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                if (!arg.StartsWith("-"))
                {
                    Console.WriteLine($"错误：参数 '{arg}' 不合法。");
                    return null;
                }

                var option = command.Options.FirstOrDefault(opt => opt[0] == arg);
                if (option == null)
                {
                    Console.WriteLine($"错误：未知参数 '{arg}'。");
                    return null;
                }

                string type = option[1];
                if (type == "value")
                {
                    if (i + 1 >= args.Length || args[i + 1].StartsWith("-"))
                    {
                        Console.WriteLine($"错误：参数 '{arg}' 缺少值。");
                        return null;
                    }
                    parameters[arg] = args[i + 1];
                    i++;
                }
                else
                {
                    parameters[arg] = "true";
                }
            }
            return parameters;
        }

        private static bool ValidateParameters(DataBase.Command command, Dictionary<string, string> parameters)
        {
            foreach (string param in parameters.Keys)
            {
                if (!command.Options.Any(opt => opt[0] == param))
                {
                    Console.WriteLine($"错误：未知参数 '{param}'。");
                    return false;
                }
            }

            foreach (var option in command.Options)
            {
                string optName = option[0];
                string description = option[2];
                if (description.Contains("必须的") && !parameters.ContainsKey(optName))
                {
                    Console.WriteLine($"错误：缺少必须参数 '{optName}'。");
                    return false;
                }
            }

            return true;
        }

        private static void ExecuteCommand(string commandName, Dictionary<string, string> parameters)
        {
            switch (commandName)
            {
                case "help":
                    if (parameters.ContainsKey("-c") == false)
                    {
                        foreach(var command in DataBase.Commands)
                        {
                            Console.WriteLine(command.Name + " " + command.Description);
                        }
                        Console.WriteLine("使用'-c'参数获得指定指令的具体帮助");
                    }
                    else
                    {
                        bool commandin = false;
                        foreach (var command in DataBase.Commands)
                        {
                            if (command.Name == parameters["-c"])
                            {
                                Console.WriteLine(command.Name + " " + command.Description);
                                foreach (var option in command.Options)
                                {
                                    Console.WriteLine(option[0] + " " + option[2]);
                                }
                                Console.WriteLine("如果选项为'-x'形式，则选项需要值；如果选项为'--x'形式，则选项不需要值");
                                commandin = true;
                            }
                        }
                        if (commandin == false) Console.WriteLine($"错误：未知命令{parameters["-c"]}");
                    }
                    break;
                case "about":
                    if (parameters.ContainsKey("--v"))
                    {
                        Console.WriteLine("DawnBreaker V1.0.0.0");
                    }
                    else
                    {
                        Console.WriteLine("DawnBreaker 破晓工具 V1.0.0.0 20250215");
                        Console.WriteLine("Copyright 2025 All Rights Reserved. 哀歌殇年 版权所有");
                        Console.WriteLine("官网: https://agsn.site/");
                        Console.WriteLine("作者QQ: 2690034441");
                    }
                    break;
                case "match":
                    switch (parameters["-t"])
                    {
                        case "email":
                            Console.WriteLine(parameters["-s"].MatchEmail().ToString());
                            break;
                        case "ip":
                            string iptype;
                            Console.WriteLine(parameters["-s"].MatchIP(out iptype).ToString() + $" iptype:{iptype}");
                            break;
                        case "mac":
                            Console.WriteLine(parameters["-s"].MatchMac().ToString());
                            break;
                        case "url":
                            Console.WriteLine(parameters["-s"].MatchURL().ToString());
                            break;
                        case "idcard":
                            string[] cardinfo = { };
                            if (parameters["-s"].MatchIdentifyCard(out cardinfo))
                            {
                                Console.WriteLine(parameters["-s"].MatchIdentifyCard(out cardinfo).ToString() + $" {cardinfo[0]} {cardinfo[1]} {cardinfo[2]}");
                            }
                            else
                            {
                                Console.WriteLine(parameters["-s"].MatchIdentifyCard(out cardinfo).ToString());
                            }
                            break;
                        default:
                            Console.WriteLine($"错误：不合法的参数 '{parameters["t"]}'");
                            break;

                    }
                    break;
                case "enc":
                    switch (parameters["-t"])
                    {
                        case "aes":
                            Console.WriteLine(parameters["-s"].AESEncrypt(parameters["-k"]));
                            break;
                        case "des":
                            Console.WriteLine(parameters["-s"].DESEncrypt(parameters["-k"]));
                            break;
                        default:
                            Console.WriteLine($"错误：不合法的参数 '{parameters["t"]}'");
                            break;
                    }
                    break;
                case "dec":
                    switch (parameters["-t"])
                    {
                        case "aes":
                            Console.WriteLine(parameters["-s"].AESDecrypt(parameters["-k"]));
                            break;
                        case "des":
                            Console.WriteLine(parameters["-s"].DESDecrypt(parameters["-k"]));
                            break;
                        default:
                            Console.WriteLine($"错误：不合法的参数 '{parameters["t"]}'");
                            break;
                    }
                    break;
                case "sys":
                    string query;
                    switch (parameters["-w"])
                    {
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
                            Console.WriteLine($"错误：不合法的参数 '{parameters["-w"]}'");
                            return;
                    }
                    ManagementObjectSearcher searcher = new ManagementObjectSearcher(query);
                    try
                    {
                        if (parameters.ContainsKey("--v")) 
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
                                    Console.WriteLine($"{property.Name}: {displayValue}");
                                }
                            }
                        }
                        else
                        {
                            int index = 0;
                            switch (parameters["-w"])
                            {
                                case "bb":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine($"主板\t型号: {obj["Product"] ?? "未知"}");
                                        return;
                                    }
                                    break;
                                case "cpu":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine(
                                            $"CPU\t核心数: {obj["NumberOfCores"] ?? "未知"}\n" +
                                            $"\t型号: {obj["Name"]?.ToString().Trim() ?? "未知"}\n" +
                                            $"\t逻辑处理器: {obj["NumberOfLogicalProcessors"] ?? "未知"}\n" +
                                            $"\t主频: {(obj["MaxClockSpeed"] != null ? $"{Convert.ToDouble(obj["MaxClockSpeed"]) / 1000} GHz" : "未知")}\n" +
                                            $"\t缓存: L2 {obj["L2CacheSize"] ?? "未知"}KB | L3 {obj["L3CacheSize"] ?? "未知"}KB");
                                        return;
                                    }
                                    break;
                                case "gpu":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine(
                                            $"GPU{++index}\t型号: {obj["Name"] ?? "未知"}\n" +
                                            $"\t显存: {(obj["AdapterRAM"] != null ? $"{Convert.ToUInt64(obj["AdapterRAM"]) / (1024 * 1024 * 1024)} GB" : "未知")}\n" +
                                            $"\t位宽: {obj["CurrentBitsPerPixel"] ?? "未知"} bit");
                                    }
                                    break;
                                case "dd":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine(
                                            $"存储{++index}\t型号: {obj["Model"]?.ToString().Trim() ?? "未知"}\n" +
                                            $"\t容量: {(obj["Size"] != null ? $"{Convert.ToUInt64(obj["Size"]) / (1024 * 1024 * 1024)} GB" : "未知")}\n" +
                                            $"\t接口: {obj["InterfaceType"] ?? "未知"}\n");
                                    }
                                    break;
                                case "pm":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine(
                                            $"内存{++index}\t型号: {obj["PartNumber"]?.ToString().Trim() ?? "未知"}\n" +
                                            $"\t容量: {(obj["Capacity"] != null ? $"{Convert.ToUInt64(obj["Capacity"]) / (1024 * 1024 * 1024)} GB" : "未知")}\n" +
                                            $"\t频率: {obj["Speed"] ?? "未知"} MHz\n");
                                    }
                                    break;
                                case "na":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine($"网络适配器{++index}\t型号: {obj["ProductName"] ?? "未知"}");
                                    }
                                    break;
                                case "sd":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine($"音频适配器{++index}\t型号: {obj["ProductName"] ?? "未知"}");
                                    }
                                    break;
                                case "dm":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine($"显示器{++index}\t型号: {obj["Name"] ?? "未知"}");
                                    }
                                    break;
                                case "os":
                                    foreach (ManagementObject obj in searcher.Get())
                                    {
                                        Console.WriteLine(
                                            $"操作系统\t名称: {obj["Caption"] ?? "未知"}\n" +
                                            $"\t版本: {obj["Version"] ?? "未知"}");
                                        return;
                                    }
                                    break;
                                default:
                                    Console.WriteLine("仅支持详细信息模式，请使用'--v'参数");
                                    break;
                            }
                        }
                    }
                    catch
                    {
                        Console.WriteLine("查询失败");
                    }
                    break;
                default:
                    Console.WriteLine($"错误：未实现命令 '{commandName}'。");
                    break;
            }
        }
    }
}
