using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SortFlowApiTester
{
    public partial class Form1 : Form
    {
        private TextBox txtApiKey;
        private TextBox txtProjectId;
        private TextBox txtApiUrl;
        private Button btnSelectImage;
        private Button btnPredict;
        private PictureBox pictureBox;
        private Label lblImagePath;
        private Label lblStatus;
        private string selectedImagePath = "";

        public Form1()
        {
            InitializeComponent();
            InitializeCustomComponents();
        }

        private void InitializeCustomComponents()
        {
            this.Text = "SortFlow API Tester";
            this.Size = new System.Drawing.Size(600, 700);
            this.StartPosition = FormStartPosition.CenterScreen;

            Label lblApiKey = new Label
            {
                Text = "API Key:",
                Location = new System.Drawing.Point(20, 20),
                Size = new System.Drawing.Size(100, 20)
            };
            this.Controls.Add(lblApiKey);

            txtApiKey = new TextBox
            {
                Location = new System.Drawing.Point(130, 20),
                Size = new System.Drawing.Size(420, 20),
                PlaceholderText = "sk_..."
            };
            this.Controls.Add(txtApiKey);

            Label lblProjectId = new Label
            {
                Text = "Project ID:",
                Location = new System.Drawing.Point(20, 60),
                Size = new System.Drawing.Size(100, 20)
            };
            this.Controls.Add(lblProjectId);

            txtProjectId = new TextBox
            {
                Location = new System.Drawing.Point(130, 60),
                Size = new System.Drawing.Size(100, 20),
                Text = "2"
            };
            this.Controls.Add(txtProjectId);

            Label lblApiUrl = new Label
            {
                Text = "API URL:",
                Location = new System.Drawing.Point(20, 100),
                Size = new System.Drawing.Size(100, 20)
            };
            this.Controls.Add(lblApiUrl);

            txtApiUrl = new TextBox
            {
                Location = new System.Drawing.Point(130, 100),
                Size = new System.Drawing.Size(420, 20),
                Text = "http://127.0.0.1:5000"
            };
            this.Controls.Add(txtApiUrl);

            btnSelectImage = new Button
            {
                Text = "📁 Sélectionner une image",
                Location = new System.Drawing.Point(20, 140),
                Size = new System.Drawing.Size(200, 40),
                Font = new System.Drawing.Font("Segoe UI", 10F)
            };
            btnSelectImage.Click += BtnSelectImage_Click;
            this.Controls.Add(btnSelectImage);

            lblImagePath = new Label
            {
                Text = "Aucune image sélectionnée",
                Location = new System.Drawing.Point(230, 150),
                Size = new System.Drawing.Size(320, 20),
                ForeColor = System.Drawing.Color.Gray
            };
            this.Controls.Add(lblImagePath);

            // PictureBox
            pictureBox = new PictureBox
            {
                Location = new System.Drawing.Point(20, 190),
                Size = new System.Drawing.Size(530, 300),
                BorderStyle = BorderStyle.FixedSingle,
                SizeMode = PictureBoxSizeMode.Zoom
            };
            this.Controls.Add(pictureBox);

            btnPredict = new Button
            {
                Text = "Prédire le cluster",
                Location = new System.Drawing.Point(20, 510),
                Size = new System.Drawing.Size(530, 50),
                Font = new System.Drawing.Font("Segoe UI", 12F, System.Drawing.FontStyle.Bold),
                BackColor = System.Drawing.Color.FromArgb(102, 126, 234),
                ForeColor = System.Drawing.Color.White,
                FlatStyle = FlatStyle.Flat,
                Enabled = false
            };
            btnPredict.Click += async (s, e) => await BtnPredict_Click();
            this.Controls.Add(btnPredict);

            lblStatus = new Label
            {
                Text = "",
                Location = new System.Drawing.Point(20, 580),
                Size = new System.Drawing.Size(530, 60),
                Font = new System.Drawing.Font("Segoe UI", 9F),
                ForeColor = System.Drawing.Color.Blue
            };
            this.Controls.Add(lblStatus);
        }

        private void BtnSelectImage_Click(object sender, EventArgs e)
        {
            using (OpenFileDialog openFileDialog = new OpenFileDialog())
            {
                openFileDialog.Filter = "Image Files|*.jpg;*.jpeg;*.png";
                openFileDialog.Title = "Sélectionnez une image";

                if (openFileDialog.ShowDialog() == DialogResult.OK)
                {
                    selectedImagePath = openFileDialog.FileName;
                    lblImagePath.Text = Path.GetFileName(selectedImagePath);
                    lblImagePath.ForeColor = System.Drawing.Color.Green;

                    pictureBox.Image = System.Drawing.Image.FromFile(selectedImagePath);

                    btnPredict.Enabled = true;
                    lblStatus.Text = "Image chargée. Prêt pour la prédiction.";
                    lblStatus.ForeColor = System.Drawing.Color.Green;
                }
            }
        }

        private async Task BtnPredict_Click()
        {
            if (string.IsNullOrWhiteSpace(txtApiKey.Text))
            {
                MessageBox.Show("Veuillez entrer votre API Key", "Erreur", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (string.IsNullOrWhiteSpace(selectedImagePath))
            {
                MessageBox.Show("Veuillez sélectionner une image", "Erreur", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            btnPredict.Enabled = false;
            lblStatus.Text = "Envoi de la requête à l'API...";
            lblStatus.ForeColor = System.Drawing.Color.Blue;

            try
            {
                byte[] imageBytes = File.ReadAllBytes(selectedImagePath);
                string base64Image = Convert.ToBase64String(imageBytes);

                string apiUrl = $"{txtApiUrl.Text}/api/v1/projects/{txtProjectId.Text}/predict";

                using (HttpClient client = new HttpClient())
                {
                    client.DefaultRequestHeaders.Add("X-API-Key", txtApiKey.Text);

                    var payload = new
                    {
                        image_base64 = base64Image
                    };

                    string jsonPayload = JsonSerializer.Serialize(payload);
                    var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

                    lblStatus.Text = "Attente de la réponse...";

                    HttpResponseMessage response = await client.PostAsync(apiUrl, content);

                    string responseBody = await response.Content.ReadAsStringAsync();

                    if (response.IsSuccessStatusCode)
                    {
                        using (JsonDocument doc = JsonDocument.Parse(responseBody))
                        {
                            var root = doc.RootElement;

                            string projectName = root.GetProperty("project_name").GetString();
                            int clusterId = root.GetProperty("cluster_id").GetInt32();
                            string clusterName = root.GetProperty("cluster_name").GetString();
                            double confidenceScore = root.GetProperty("confidence_score").GetDouble();
                            bool isUncertain = root.GetProperty("is_uncertain").GetBoolean();

                            string resultMessage = $"PRÉDICTION RÉUSSIE\n\n" +
                                $"Projet: {projectName}\n" +
                                $"Cluster ID: {clusterId}\n" +
                                $"Nom: {clusterName}\n" +
                                $"Confiance: {confidenceScore:P2}\n" +
                                $"Incertain: {(isUncertain ? "Oui" : "Non")}";

                            MessageBox.Show(resultMessage, "Résultat de la prédiction",
                                MessageBoxButtons.OK, MessageBoxIcon.Information);

                            lblStatus.Text = $"Résultat: {clusterName} (Confiance: {confidenceScore:P2})";
                            lblStatus.ForeColor = System.Drawing.Color.Green;
                        }
                    }
                    else
                    {
                        string errorMessage = $"ERREUR {response.StatusCode}\n\n{responseBody}";
                        MessageBox.Show(errorMessage, "Erreur API", MessageBoxButtons.OK, MessageBoxIcon.Error);

                        lblStatus.Text = $"Erreur: {response.StatusCode}";
                        lblStatus.ForeColor = System.Drawing.Color.Red;
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"EXCEPTION\n\n{ex.Message}", "Erreur", MessageBoxButtons.OK, MessageBoxIcon.Error);
                lblStatus.Text = $"Erreur: {ex.Message}";
                lblStatus.ForeColor = System.Drawing.Color.Red;
            }
            finally
            {
                btnPredict.Enabled = true;
            }
        }
    }
}