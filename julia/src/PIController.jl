# calcular_pi.jl  (SEM pacotes)
# Uso:
#   julia calcular_pi.jl dados.csv potencia_col temperatura_col tempo_col
# Ex:
#   julia calcular_pi.jl dados.csv potencia temperatura timestamp
#
# Se o tempo for timestamp, você pode passar "idx" e ele usa índice como tempo.

using Statistics
using Dates

# caminho absoluto da pasta onde está o script
SCRIPT_DIR = @__DIR__

# caminho até a pasta processed
DATA_DIR = normpath(joinpath(SCRIPT_DIR, "..", "..", "analysis", "data", "processed"))

function parse_float(s)
    str = String(s)
    str = strip(str)                 # remove espaços
    str = replace(str, "\"" => "")   # remove aspas "
    str = replace(str, "\uFEFF" => "") # remove BOM se existir
    str = replace(str, "," => ".")   # vírgula decimal -> ponto
    return parse(Float64, str)
end


# ---------- util: parse CSV simples ----------
function read_csv_simple(path::String; delim::Char=';')
    lines = readlines(path)
    header = split(strip(lines[1]), delim)
    data = [split(strip(l), delim) for l in lines[2:end] if !isempty(strip(l))]
    return header, data
    end

    function detect_delim(line::String)
        c1 = count(==(','), line)
        c2 = count(==(';'), line)
        return c2 > c1 ? ';' : ','
    end

    function col_index(header::Vector{SubString{String}}, name::String)
        idx = findfirst(==(name), String.(header))
        idx === nothing && error("Coluna '$name' não encontrada. Cabeçalho: $(join(String.(header), ", "))")
        return idx
    end

    # ---------- util: parse tempo ----------

    function parse_time_column(col)
        # 1) tenta número direto
        vals = Float64[]
        ok_num = true
        for s in col
            x = tryparse(Float64, replace(strip(String(s)), "," => "."))
            if x === nothing
                ok_num = false
                break
            end
            push!(vals, x)
        end
        if ok_num
            t = vals
            t .-= t[1]
            return t
        end

        # 2) tenta timestamp ISO com timezone (ex: "2025-12-19 17:04:00+00:00")
        dts = DateTime[]
        for s in col
            str = strip(String(s))
            str = replace(str, "\"" => "")      # remove aspas se vierem
            str = replace(str, "\uFEFF" => "")  # remove BOM se existir

            # remove timezone tipo +00:00 ou -03:00 (mantém só "YYYY-mm-dd HH:MM:SS")
            str = replace(str, r"[+-]\d\d:\d\d$" => "")

                          # se vier com 'T' no meio, troca por espaço
                          str = replace(str, "T" => " ")

                          # parse ISO sem timezone
                          dt = tryparse(DateTime, str, dateformat"yyyy-mm-dd HH:MM:SS")
                          dt === nothing && error("Não consegui interpretar tempo (após limpar timezone): '$str'")
                          push!(dts, dt)
        end

        t_ms = Dates.value.(dts .- dts[1])  # milliseconds
        return t_ms ./ 1000.0
    end


        # ---------- identificação FOPDT simples ----------
        function identify_fopdt(t, T, u; step_threshold=1.0)
            N = length(t)
            @assert length(T) == N && length(u) == N

            du = diff(u)
            idx = findfirst(x -> abs(x) >= step_threshold, du)
            idx === nothing && error("Não encontrei degrau de potência. Aumente step_threshold ou verifique a coluna u.")

            k0 = idx + 1
            t0 = t[k0]
            u0 = u[k0-1]
            u1 = u[k0]
            Δu = u1 - u0

            # médias antes/depois (janelas simples)
            pre_start = max(1, k0 - 10)
            pre_end   = max(1, k0 - 1)
            post_start = max(k0 + 10, Int(floor(0.8N)))
            post_end   = N

            T0 = mean(@view T[pre_start:pre_end])
            T1 = mean(@view T[post_start:post_end])

            ΔT = T1 - T0
            K = ΔT / Δu

            # τ: tempo pra atingir 63,2%
            T63 = T0 + 0.632 * ΔT
            k63 = findfirst(x -> (ΔT >= 0 ? x >= T63 : x <= T63), T)
            k63 === nothing && error("Não encontrei cruzamento de 63%. Talvez não estabilizou ou o degrau é pequeno.")
            t63 = t[k63]

            # estimativas
            L = max(0.0, t0 - t[1])   # atraso aproximado
            τ = max(1e-6, t63 - t0)   # garante positivo

            return (; K, τ, L, t0, Δu, T0, T1, k0, k63)
        end

        function imc_pi(K, τ, L; λ=τ)
            # PI IMC (forma simples e estável)
            Kp = τ / (K * (λ + L))
            Ki = 1 / (λ + L)
            return Kp, Ki, λ
        end

        # ---------- main ----------
        if length(ARGS) < 2
            println("Uso:")
            println("  julia calcular_pi.jl delay_tratado.csv potencia_col temperatura_col [tempo_col]")
            println("Se não passar tempo_col, usa índice (0,1,2...) como tempo.")
            exit(1)
        end

        file = joinpath(DATA_DIR, ARGS[1])
        pot_col = ARGS[2]
        temp_col = length(ARGS) >= 3 ? ARGS[3] : error("Passe também a coluna de temperatura.")
        time_col = length(ARGS) >= 4 ? ARGS[4] : "idx"

        firstline = readline(file)
        delim = detect_delim(firstline)

        header, rows = read_csv_simple(file; delim=delim)

        ip = col_index(header, pot_col)
        it = col_index(header, temp_col)

        u = Float64[]
        T = Float64[]
        tc = SubString{String}[]

        for r in rows
            push!(u, parse_float(r[ip]))
            push!(T, parse_float(r[it]))
            if time_col != "idx"
                ic = col_index(header, time_col)
                push!(tc, r[ic])
            end
        end

        t = time_col == "idx" ? collect(0.0:length(u)-1) : parse_time_column(tc)

        info = identify_fopdt(t, T, u; step_threshold=1.0)
        Kp, Ki, λ = imc_pi(info.K, info.τ, info.L; λ=info.τ)

        println("=== Identificação (FOPDT) ===")
        println("K  = $(info.K)")
        println("τ  = $(info.τ) s")
        println("L  = $(info.L) s")
        println("Degrau em t0=$(info.t0)s, Δu=$(info.Δu), T0=$(info.T0), T1=$(info.T1)")

        println("\n=== Sintonia PI (IMC) ===")
        println("λ  = $λ s")
        println("Kp = $Kp")
        println("Ki = $Ki  (1/s)")

        # salva resumo em arquivo
        open("resultado_pi.txt", "w") do io
            write(io, "K=$(info.K)\nτ=$(info.τ)\nL=$(info.L)\nKp=$Kp\nKi=$Ki\nλ=$λ\n")
        end

        println("\nSalvei: resultado_pi.txt")
