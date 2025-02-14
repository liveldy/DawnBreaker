namespace DawnBreaker
{
    partial class MainForm
    {
        /// <summary>
        ///  Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        ///  Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        ///  Required method for Designer support - do not modify
        ///  the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(MainForm));
            MainTabControl = new TabControl();
            StringProcessPage = new TabPage();
            AboutButton = new Button();
            StringButton = new Button();
            StringComboBox = new ComboBox();
            OutputTextBox = new TextBox();
            InputTextBox = new TextBox();
            SystemInfoPage = new TabPage();
            SystemInfoComboBox = new ComboBox();
            SystemInfoTextBox = new TextBox();
            MainTabControl.SuspendLayout();
            StringProcessPage.SuspendLayout();
            SystemInfoPage.SuspendLayout();
            SuspendLayout();
            // 
            // MainTabControl
            // 
            MainTabControl.Controls.Add(StringProcessPage);
            MainTabControl.Controls.Add(SystemInfoPage);
            MainTabControl.Location = new Point(10, 10);
            MainTabControl.Name = "MainTabControl";
            MainTabControl.SelectedIndex = 0;
            MainTabControl.Size = new Size(1350, 720);
            MainTabControl.TabIndex = 0;
            // 
            // StringProcessPage
            // 
            StringProcessPage.Controls.Add(AboutButton);
            StringProcessPage.Controls.Add(StringButton);
            StringProcessPage.Controls.Add(StringComboBox);
            StringProcessPage.Controls.Add(OutputTextBox);
            StringProcessPage.Controls.Add(InputTextBox);
            StringProcessPage.Location = new Point(4, 33);
            StringProcessPage.Name = "StringProcessPage";
            StringProcessPage.Padding = new Padding(3);
            StringProcessPage.Size = new Size(1342, 683);
            StringProcessPage.TabIndex = 0;
            StringProcessPage.Text = "文本处理";
            StringProcessPage.UseVisualStyleBackColor = true;
            // 
            // AboutButton
            // 
            AboutButton.Location = new Point(1140, 290);
            AboutButton.Name = "AboutButton";
            AboutButton.Size = new Size(180, 90);
            AboutButton.TabIndex = 5;
            AboutButton.Text = "关于";
            AboutButton.UseVisualStyleBackColor = true;
            AboutButton.Click += AboutButton_Click;
            // 
            // StringButton
            // 
            StringButton.Location = new Point(20, 340);
            StringButton.Name = "StringButton";
            StringButton.Size = new Size(250, 40);
            StringButton.TabIndex = 3;
            StringButton.Text = "处理";
            StringButton.UseVisualStyleBackColor = true;
            StringButton.Click += StringButton_Click;
            // 
            // StringComboBox
            // 
            StringComboBox.DropDownStyle = ComboBoxStyle.DropDownList;
            StringComboBox.Location = new Point(20, 290);
            StringComboBox.Name = "StringComboBox";
            StringComboBox.Size = new Size(250, 32);
            StringComboBox.TabIndex = 2;
            // 
            // OutputTextBox
            // 
            OutputTextBox.Location = new Point(20, 400);
            OutputTextBox.Multiline = true;
            OutputTextBox.Name = "OutputTextBox";
            OutputTextBox.PlaceholderText = "输出文本";
            OutputTextBox.Size = new Size(1300, 250);
            OutputTextBox.TabIndex = 1;
            OutputTextBox.Text = "提示：\r\n1.如果需要处理多个内容，请按行分隔；如果需要实现自动化多处理，请使用命令行；运行窗体程序时的命令行用于显示日志，如需要使用命令行，自行在程序目录打开控制台输入dawnbreaker help\r\n2.部分功能未显示，未来的更新会进行补充\r\n3.使用加解密时，第一行是待加解密文本，第二行是密钥\r\n";
            // 
            // InputTextBox
            // 
            InputTextBox.Location = new Point(20, 20);
            InputTextBox.Multiline = true;
            InputTextBox.Name = "InputTextBox";
            InputTextBox.PlaceholderText = "输入文本";
            InputTextBox.Size = new Size(1300, 250);
            InputTextBox.TabIndex = 0;
            // 
            // SystemInfoPage
            // 
            SystemInfoPage.Controls.Add(SystemInfoComboBox);
            SystemInfoPage.Controls.Add(SystemInfoTextBox);
            SystemInfoPage.Location = new Point(4, 33);
            SystemInfoPage.Name = "SystemInfoPage";
            SystemInfoPage.Padding = new Padding(3);
            SystemInfoPage.Size = new Size(1342, 683);
            SystemInfoPage.TabIndex = 1;
            SystemInfoPage.Text = "系统信息";
            SystemInfoPage.UseVisualStyleBackColor = true;
            // 
            // SystemInfoComboBox
            // 
            SystemInfoComboBox.DropDownStyle = ComboBoxStyle.DropDownList;
            SystemInfoComboBox.FormattingEnabled = true;
            SystemInfoComboBox.Location = new Point(20, 20);
            SystemInfoComboBox.Name = "SystemInfoComboBox";
            SystemInfoComboBox.Size = new Size(1300, 32);
            SystemInfoComboBox.TabIndex = 1;
            SystemInfoComboBox.SelectedIndexChanged += SystemInfoComboBox_SelectedIndexChanged;
            // 
            // SystemInfoTextBox
            // 
            SystemInfoTextBox.Location = new Point(20, 100);
            SystemInfoTextBox.Multiline = true;
            SystemInfoTextBox.Name = "SystemInfoTextBox";
            SystemInfoTextBox.ReadOnly = true;
            SystemInfoTextBox.Size = new Size(1300, 550);
            SystemInfoTextBox.TabIndex = 0;
            // 
            // MainForm
            // 
            AutoScaleDimensions = new SizeF(11F, 24F);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(1378, 744);
            Controls.Add(MainTabControl);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            Icon = (Icon)resources.GetObject("$this.Icon");
            MaximizeBox = false;
            Name = "MainForm";
            Text = "破晓工具";
            MainTabControl.ResumeLayout(false);
            StringProcessPage.ResumeLayout(false);
            StringProcessPage.PerformLayout();
            SystemInfoPage.ResumeLayout(false);
            SystemInfoPage.PerformLayout();
            ResumeLayout(false);
        }

        #endregion

        private TabControl MainTabControl;
        private TabPage StringProcessPage;
        private TabPage SystemInfoPage;
        private TextBox OutputTextBox;
        private TextBox InputTextBox;
        private ComboBox StringComboBox;
        private Button StringButton;
        private ComboBox SystemInfoComboBox;
        private TextBox SystemInfoTextBox;
        private Button AboutButton;
    }
}
