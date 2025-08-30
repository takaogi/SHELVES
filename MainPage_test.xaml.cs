
using Microsoft.Maui.Controls;
using Python.Runtime;
using System;
using System.Threading.Tasks;

namespace ShelvesMauiTest;

public partial class MainPage : ContentPage
{
    dynamic api;

    Label outputLabel;
    Entry inputEntry;
    Button sendButton;
    ActivityIndicator spinner;

    string pendingInput = "";
    bool waitingForInput = false;

    public MainPage()
    {
        InitializeComponent();

        outputLabel = new Label { Text = "出力:\n", VerticalOptions = LayoutOptions.Start };
        inputEntry = new Entry { Placeholder = "入力してください..." };
        sendButton = new Button { Text = "送信" };
        spinner = new ActivityIndicator { IsRunning = false, IsVisible = false };

        sendButton.Clicked += (s, e) =>
        {
            if (waitingForInput)
            {
                pendingInput = inputEntry.Text ?? "";
                waitingForInput = false;
            }
        };

        Content = new VerticalStackLayout
        {
            Children = { outputLabel, inputEntry, sendButton, spinner }
        };

        Task.Run(() => InitPython());
    }

    void InitPython()
    {
        PythonEngine.Initialize();
        using (Py.GIL())
        {
            dynamic sys = Py.Import("sys");
            sys.path.append(@"X:\Dev\S.H.E.L.V.E.S");  // Pythonのソースがある場所を追加

            dynamic shelvesModule = Py.Import("shelves_api");
            api = shelvesModule.ShelvesAPI(false);
            api.initialize();

            // コールバック登録
            api.set_callbacks(
                new Action<string>((msg) =>
                {
                    MainThread.BeginInvokeOnMainThread(() =>
                    {
                        outputLabel.Text += msg + "\n";
                    });
                }),
                new Func<string, string>((prompt) =>
                {
                    MainThread.BeginInvokeOnMainThread(() =>
                    {
                        outputLabel.Text += $"[入力待ち] {prompt}\n";
                        waitingForInput = true;
                    });

                    // 待機ループ
                    while (waitingForInput) { Task.Delay(100).Wait(); }
                    return pendingInput;
                }),
                new Action<string>((action) =>
                {
                    MainThread.BeginInvokeOnMainThread(() =>
                    {
                        if (action == "start")
                        {
                            spinner.IsVisible = true;
                            spinner.IsRunning = true;
                        }
                        else
                        {
                            spinner.IsVisible = false;
                            spinner.IsRunning = false;
                        }
                    });
                })
            );

            // ログ転送
            api.set_log_callback(new Action<string>((msg) =>
            {
                MainThread.BeginInvokeOnMainThread(() =>
                {
                    outputLabel.Text += "[LOG] " + msg + "\n";
                });
            }));

            // ループ開始
            api.run_loop();
        }
    }
}
