# 💡 Dimmer de Cargas AC com ESP32 (Monitoramento via Serial + InfluxDB)

Este projeto implementa um dimmer de controle de fase para cargas AC (resistivas) usando um ESP32. O controle de potência e a leitura de temperatura são realizados pelo firmware do ESP32, e os dados de monitoramento são enviados pela porta **Serial/USB**.

Os dados da Serial são destinados a serem consumidos por um **serviço de ponte externo** que, por sua vez, os insere no banco de dados de séries temporais **InfluxDB** para monitoramento e visualização.

---

## 🛠️ Hardware e Configuração

### 1. Componentes Principais

| Componente | Função |
| :--- | :--- |
| **Microcontrolador** | ESP32-WROOM-32D |
| **Detector de Zero-Cross** | Módulo Zero-Cross (H11AA1 - U2 no esquema) |
| **Acionador de Potência** | Optotriac (MOC3023M - U4) + Triac (BTA16-600B - Q1) |
| **Sensor de Temperatura** | Termistor NTC de 10kΩ (TH2) |

### 2. Pinagem (Conforme o Esquema)

O firmware (`.ino`) e o esquema do KiCad definem a seguinte pinagem:

| Variável | Porta (Padrão) | Função no Circuito |
| :--- | :--- | :--- |
| `PIN_ZC` | `GPIO 27` | Entrada do detector de Zero-Cross (Interrupção) |
| `PIN_MOC` | `GPIO 26` | Saída para o Optotriac (Acionamento do Triac) |
| `PIN_TEMP` | `GPIO 34` | Entrada Analógica para o Termistor NTC |

---

## 💻 Ambiente de Monitoramento (InfluxDB)

O InfluxDB é utilizado para persistir e visualizar os dados de temperatura e os estados operacionais do dimmer.

### 1. Pré-requisitos

Certifique-se de ter instalado:

* **Docker**
* **Docker Compose**
* O **Serviço de Ponte Serial** (a ser desenvolvido/implementado separadamente, que lê o Serial do ESP32 e escreve no InfluxDB).

### 2. Configuração do Ambiente (`.env`)

Configure as variáveis de ambiente necessárias para o InfluxDB no arquivo **`.env`** (localmente, fora do Git):

| Variável | Exemplo de Valor | Descrição |
| :--- | :--- | :--- |
| `INFLUX_PORT` | `8086` | Porta local para acesso ao InfluxDB (UI/API). |
| `INFLUX_TOKEN` | `token_secreto_para_api` | Token de API inicial (necessário para o seu serviço de ponte). |
| `INFLUX_BUCKET` | `dimmer_data` | Bucket (banco de dados) para os dados do dimmer. |
| `INFLUX_ORG` | `minha_org` | Organização inicial do InfluxDB. |
| (Outras) | ... | Outras variáveis de configuração do Docker. |

### 3. Inicialização do InfluxDB

Execute o container do InfluxDB usando o Docker Compose:

```bash
docker-compose up -d
