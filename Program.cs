using DawnBreaker.Consoles;

namespace DawnBreaker
{
    internal static class Program
    {
        /// <summary>
        ///  ������
        /// </summary>
        [STAThread]
        static void Main(string[] args)
        {
            if (args.Length == 0) 
            {
                ApplicationConfiguration.Initialize();
                Application.Run(new MainForm());
            }
            else
            {
                CommandPause.ProcessCommand(args);
            }
        }
    }
}