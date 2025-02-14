using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Mail;
using System.Security.Cryptography;
using System.Security.Policy;
using System.Text;
using System.Text.RegularExpressions;
using DawnBreaker.Common;
namespace DawnBreaker.Common
{
    public static class StringExtensions
    {
        /// <summary>
        /// 检验字符串是否符合邮箱格式
        /// </summary>
        public static bool MatchEmail(this string s)
        {
            if (string.IsNullOrEmpty(s)) return false;
            string pattern = @"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$";
            return Regex.IsMatch(s, pattern);
        }

        /// <summary>
        /// 检验字符串是否符合邮箱格式，并检查是否为符合指定域名的邮箱
        /// </summary>
        /// <param name="domain">域名</param>
        public static bool MatchEmail(this string s, string domain)
        {
            if (string.IsNullOrEmpty(s)) return false;
            string pattern = @"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$";
            if (Regex.IsMatch(s, pattern))
            {
                string[] splits = s.Split("@");
                return splits[1] == domain;
            }
            return false;
        }

        /// <summary>
        /// 检验字符串是否符合IP地址格式
        /// </summary>
        public static bool MatchIP(this string s)
        {
            if (string.IsNullOrEmpty(s)) return false;
            IPAddress? address;
            if (IPAddress.TryParse(s, out address) && address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
            {
                return true;
            }
            if (IPAddress.TryParse(s, out address) && address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetworkV6)
            {
                return true;
            }
            return false;
        }

        /// <summary>
        /// 检验字符串是否符合IP地址格式
        /// </summary>
        /// <param name="IPType">
        /// 获取IP类型
        /// Invalid: 无效的IP地址
        /// IPv4: IPv4地址
        /// IPv6: IPv6地址
        /// </param>
        public static bool MatchIP(this string s,out string IPType)
        {
            if (string.IsNullOrEmpty(s)) {
                IPType = "Invalid";
                return false; 
            }
            IPAddress? address;
            if (IPAddress.TryParse(s, out address) && address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
            {
                IPType = "IPv4";
                return true;
            }
            if (IPAddress.TryParse(s, out address) && address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetworkV6)
            {
                IPType = "IPv6";
                return true;
            }
            IPType = "Invalid";
            return false;
        }

        /// <summary>
        /// 检验字符串是否符合MAC地址格式
        /// </summary>
        public static bool MatchMac(this string s)
        {
            if (string.IsNullOrEmpty(s)) return false;
            string pattern = @"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$";
            return Regex.IsMatch(s, pattern);
        }

        /// <summary>
        /// 检验字符串是否符合URL地址格式
        /// </summary>
        public static bool MatchURL(this string s)
        {
            if (string.IsNullOrEmpty(s)) return false;
            Uri? parsedUri;
            bool isValid = Uri.TryCreate(s, UriKind.Absolute, out parsedUri);
            if (isValid && parsedUri?.Scheme != null)
            {
                return true;
            }
            return false;
        }

        /// <summary>
        /// 检验字符串是否符合URL地址格式
        /// </summary>
        /// <param name="URLProtocol">
        /// 获取URL协议
        /// Invalid: 无效的URL地址
        /// 有效的URL地址: 如https、ftp等
        /// </param>
        public static bool MatchURL(this string s,out string URLProtocol)
        {
            if (string.IsNullOrEmpty(s)) {
                URLProtocol = "Invalid";
                return false;
            }
            Uri ?parsedUri;
            bool isValid = Uri.TryCreate(s, UriKind.Absolute, out parsedUri);
            if (isValid && parsedUri?.Scheme != null)
            {
                URLProtocol = parsedUri.Scheme.ToLower();
                return true;
            }
            URLProtocol = "Invalid";
            return false;
        }

        /// <summary>
        /// 检验字符串是否符合身份证号码规范（中国大陆）
        /// </summary>
        public static bool MatchIdentifyCard(this string s)
        {
            if (string.IsNullOrEmpty(s))
            {
                return false;
            }

            if (s.Length != 15 && s.Length != 18)
            {
                return false;
            }

            string pattern = @"^(^\d{15}$|^\d{17}(\d|X|x)$)";
            Regex regex = new Regex(pattern);
            if (!regex.IsMatch(s))
            {
                return false;
            }

            if (s.Length == 18)
            {
                if (!ValidateCheckCode(s))
                {
                    return false;
                }
            }

            return true;
        }

        /// <summary>
        /// 检验字符串是否符合身份证号码规范（中国大陆）
        /// </summary>
        /// <param name="CardInfo">
        /// 获取身份证号码信息，依次为所在地区、出生年月日、性别和号位，如果身份证号码不合法，则位Invalid
        /// </param>
        public static bool MatchIdentifyCard(this string s, out string[] CardInfo)
        {
            if (string.IsNullOrEmpty(s))
            {
                CardInfo = new string[1];
                CardInfo[0] = "Invalid";
                return false;
            }

            if (s.Length != 15 && s.Length != 18)
            {
                CardInfo = new string[1];
                CardInfo[0] = "Invalid";
                return false;
            }

            string pattern = @"^(^\d{15}$|^\d{17}(\d|X|x)$)";
            Regex regex = new Regex(pattern);
            if (!regex.IsMatch(s))
            {
                CardInfo = new string[1];
                CardInfo[0] = "Invalid";
                return false;
            }

            if (s.Length == 18)
            {
                if (!ValidateCheckCode(s))
                {
                    CardInfo = new string[1];
                    CardInfo[0] = "Invalid";
                    return false;
                }
            }
            CardInfo = new string[3];
            if (s.Length == 15)
            {
                CardInfo[1] = "19" + s.Substring(6, 6);
            }
            else
            {
                CardInfo[1] = s.Substring(6, 8);
            }

            string genderDigit = s.Length == 15 ? s.Substring(14, 1) : s.Substring(16, 1);
            CardInfo[2] = int.Parse(genderDigit) % 2 == 0 ? "女" : "男";

            string provinceCode = s.Substring(0, 2);
            CardInfo[0] = DataBase.ProvinceCodes.ContainsKey(provinceCode) ? DataBase.ProvinceCodes[provinceCode] : "未知地区";

            return true;
        }

        /// <summary>
        /// 身份证号码校验
        /// </summary>
        private static bool ValidateCheckCode(string idCard)
        {
            int[] weights = { 7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2 };
            char[] checkCodes = { '1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2' };
            int sum = 0;
            for (int i = 0; i < 17; i++)
            {
                sum += (idCard[i] - '0') * weights[i];
            }
            int mod = sum % 11;
            return idCard.ToUpper()[17] == checkCodes[mod];
        }

        /// <summary>
        /// 使用AES加密字符串
        /// </summary>
        /// <param name="key">
        /// 加密密钥（16、24或32字节），如果不满足字节数，则会用0补齐
        /// </param>
        /// <returns>
        /// 返回密文，如果明文为空，则返回NULL
        /// </returns>
        public static string AESEncrypt(this string plainText, string key)
        {
            if (string.IsNullOrEmpty(plainText)) return "NULL";
            byte[] keyBytes = Encoding.UTF8.GetBytes(key);
            int keySize = keyBytes.Length;
            if (keySize != 16 && keySize != 24 && keySize != 32)
            {
                Array.Resize(ref keyBytes, 32);
                for (int i = keyBytes.Length; i < keyBytes.Length; i++)
                {
                    keyBytes[i] = 0;
                }
            }

            byte[] iv = new byte[16];
            using (RandomNumberGenerator rng = RandomNumberGenerator.Create())
            {
                rng.GetBytes(iv);
            }

            using (Aes aes = Aes.Create())
            {
                aes.Key = keyBytes;
                aes.IV = iv;
                aes.Mode = CipherMode.CBC;
                aes.Padding = PaddingMode.PKCS7;

                ICryptoTransform encryptor = aes.CreateEncryptor(aes.Key, aes.IV);

                using (MemoryStream msEncrypt = new MemoryStream())
                {
                    msEncrypt.Write(iv, 0, iv.Length);

                    using (CryptoStream csEncrypt = new CryptoStream(msEncrypt, encryptor, CryptoStreamMode.Write))
                    using (StreamWriter swEncrypt = new StreamWriter(csEncrypt))
                    {
                        swEncrypt.Write(plainText);
                    }

                    return Convert.ToBase64String(msEncrypt.ToArray());
                }
            }
        }

        /// <summary>
        /// 使用AES解密字符串
        /// </summary>
        /// <param name="key">
        /// 加密密钥（16、24或32字节），如果不满足字节数，则会用0补齐
        /// </param>
        /// <returns>
        /// 返回明文，如果密文为空、密钥错误或密文损坏，则返回NULL
        /// </returns>
        public static string AESDecrypt(this string cipherText, string key)
        {
            if (string.IsNullOrEmpty(cipherText)) return "NULL";

            byte[] keyBytes = Encoding.UTF8.GetBytes(key);
            int keySize = keyBytes.Length;
            if (keySize != 16 && keySize != 24 && keySize != 32)
            {
                Array.Resize(ref keyBytes, 32);
                for (int i = key.Length; i < keyBytes.Length; i++)
                {
                    keyBytes[i] = 0;
                }
            }

            try
            {
                byte[] fullCipher = Convert.FromBase64String(cipherText);

                byte[] iv = new byte[16];
                Array.Copy(fullCipher, 0, iv, 0, iv.Length);

                byte[] cipher = new byte[fullCipher.Length - iv.Length];
                Array.Copy(fullCipher, iv.Length, cipher, 0, cipher.Length);

                using (Aes aes = Aes.Create())
                {
                    aes.Key = keyBytes;
                    aes.IV = iv;
                    aes.Mode = CipherMode.CBC;
                    aes.Padding = PaddingMode.PKCS7;

                    ICryptoTransform decryptor = aes.CreateDecryptor(aes.Key, aes.IV);

                    using (MemoryStream msDecrypt = new MemoryStream(cipher))
                    using (CryptoStream csDecrypt = new CryptoStream(msDecrypt, decryptor, CryptoStreamMode.Read))
                    using (StreamReader srDecrypt = new StreamReader(csDecrypt))
                    {
                        return srDecrypt.ReadToEnd();
                    }
                }
            }
            catch
            {
                return "NULL";
            }
        }

        /// <summary>
        /// 使用DES加密字符串，提示：DES加密算法已经被证实不安全，建议使用更安全的AES加密算法
        /// </summary>
        /// <param name="key">
        /// 加密密钥（8字节），如果不满足字节数，则会用0补齐
        /// </param>
        /// <returns>
        /// 返回密文，如果明文为空，则返回NULL
        /// </returns>
        public static string DESEncrypt(this string plainText, string key)
        {
            if (string.IsNullOrEmpty(plainText)) return "NULL";
            key = key.PadRight(8, '0').Substring(0, 8);
            using (DESCryptoServiceProvider des = new DESCryptoServiceProvider())
            {
                des.GenerateIV();
                byte[] iv = des.IV;
                using (ICryptoTransform encryptor = des.CreateEncryptor(Encoding.UTF8.GetBytes(key), iv))
                {
                    byte[] plainTextBytes = Encoding.UTF8.GetBytes(plainText);
                    byte[] cipherTextBytes = encryptor.TransformFinalBlock(plainTextBytes, 0, plainTextBytes.Length);
                    byte[] result = new byte[iv.Length + cipherTextBytes.Length];
                    Buffer.BlockCopy(iv, 0, result, 0, iv.Length);
                    Buffer.BlockCopy(cipherTextBytes, 0, result, iv.Length, cipherTextBytes.Length);
                    return Convert.ToBase64String(result);
                }
            }
        }

        /// <summary>
        /// 使用DES解密字符串，提示：DES加密算法已经被证实不安全，建议使用更安全的AES加密算法
        /// </summary>
        /// <param name="key">
        /// 加密密钥（8字节），如果不满足字节数，则会用0补齐
        /// </param>
        /// <returns>
        /// 返回密文，如果明文为空，则返回NULL
        /// </returns>
        public static string DESDecrypt(this string cipherText, string key)
        {
            if (string.IsNullOrEmpty(cipherText)) return "NULL";
            key = key.PadRight(8, '0').Substring(0, 8);
            byte[] cipherTextBytes = Convert.FromBase64String(cipherText);
            using (DESCryptoServiceProvider des = new DESCryptoServiceProvider())
            {
                byte[] iv = new byte[8];
                Buffer.BlockCopy(cipherTextBytes, 0, iv, 0, iv.Length);
                byte[] cipherTextBytesWithoutIv = new byte[cipherTextBytes.Length - iv.Length];
                Buffer.BlockCopy(cipherTextBytes, iv.Length, cipherTextBytesWithoutIv, 0, cipherTextBytesWithoutIv.Length);
                using (ICryptoTransform decryptor = des.CreateDecryptor(Encoding.UTF8.GetBytes(key), iv))
                {
                    byte[] plainTextBytes = decryptor.TransformFinalBlock(cipherTextBytesWithoutIv, 0, cipherTextBytesWithoutIv.Length);
                    return Encoding.UTF8.GetString(plainTextBytes);
                }
            }
        }
    }



    internal class StringProcess
    {

    }
}
