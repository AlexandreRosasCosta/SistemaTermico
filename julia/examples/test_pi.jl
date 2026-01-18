# Deixa o Julia enxergar a pasta src/
push!(LOAD_PATH, joinpath(@__DIR__, "..", "src"))

using PIController

function main()
    pi = PI(2.0, 5.0; umin=0.0, umax=100.0)

    setpoint    = 50.0
    measurement = 30.0
    dt          = 0.1

    for k in 1:10
        e = setpoint - measurement
        u = update!(pi, e, dt)
        println("step $k | error=$e | control=$u | measurement=$measurement")
        measurement += 0.5   # planta fake só pra ver o controle reagir
    end
end

main()
