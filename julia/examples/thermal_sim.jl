push!(LOAD_PATH, joinpath(@__DIR__, "..", "src"))
using PIController

function main()
    # PI
    pi = PI(2.0, 5.0; umin=0.0, umax=100.0)

    # thermal model
    Tamb = 25.0
    tau  = 60.0      # time constant (seconds)
    K    = 0.8       # actuator gain
    T    = Tamb      # initial condition
    dt   = 1.0       # sampling time in seconds
    setp = 50.0      # setpoint

    for k in 1:200
        err = setp - T
        u = update!(pi, err, dt)
        T += dt * (-(T - Tamb)/tau + K * u)

        @info "k=$k" T=T control=u
    end
end

main()

