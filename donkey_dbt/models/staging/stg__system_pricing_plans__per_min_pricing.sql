with pricing as (

    select *
    from {{ source('donkey_raw', 'system_pricing_plans__per_min_pricing') }}

),

plans as (

    select
        plan_id,
        _dlt_id
    from {{ source('donkey_raw', 'system_pricing_plans') }}

),

renamed as (

    select
        pl.plan_id,
        p._dlt_list_idx as segment_index,
        p.start as start_minute,
        p.{{ adapter.quote('end') }} as end_minute,
        p.interval as interval_minutes,
        p.rate

    from pricing as p
    inner join plans as pl
        on p._dlt_parent_id = pl._dlt_id

)

select * from renamed
